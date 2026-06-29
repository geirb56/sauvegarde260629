"""GccliProvider — real Garmin connector backed by the isolated GccliRunner.

NON-NEGOTIABLE constraint: the frontend never supplies a Garmin password.
Credentials for the real path are sourced ONLY from a backend-controlled
location (environment variables, dev-only), stored transiently in the ephemeral
vault, used for a single sync, then destroyed immediately.

If gccli is unavailable or Garmin requires interactive auth, connect() returns
an mfa_required/error state so the service can ask the user to retry — the
Garmin password is never collected in the UI.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from ..runner import GccliRunner, GccliUnavailable, GccliError
from ..vault import EphemeralCredentialVault
from .base import (
    ConnectResult,
    Provider,
    STATUS_CONNECTED,
    STATUS_ERROR,
    STATUS_MFA_REQUIRED,
)

logger = logging.getLogger(__name__)


class GccliProvider(Provider):
    name = "gccli"

    def __init__(self, vault: EphemeralCredentialVault, runner: GccliRunner):
        self._vault = vault
        self._runner = runner

    def _backend_credentials(self) -> Optional[tuple[str, str]]:
        """Credentials are backend-controlled only (dev/server env). Never UI."""
        username = os.environ.get("GARMIN_USERNAME")
        password = os.environ.get("GARMIN_PASSWORD")
        if username and password:
            return username, password
        return None

    def connect(self, user_id: str, simulate_mfa: bool = False) -> ConnectResult:
        if not self._runner.is_available():
            return ConnectResult(
                status=STATUS_ERROR,
                detail="Garmin connector temporarily unavailable.",
            )
        creds = self._backend_credentials()
        if not creds:
            return ConnectResult(
                status=STATUS_ERROR,
                detail="Garmin connector not configured.",
            )
        username, password = creds
        # Store transiently; will be used by sync then destroyed.
        self._vault.store(user_id, username, password)
        return ConnectResult(status=STATUS_CONNECTED, detail="Garmin connected")

    def sync_activities(self, user_id: str, since: Optional[str] = None) -> List[Dict]:
        token = self._vault.token_for_user(user_id)
        if token is None:
            raise GccliError("No active Garmin session for user")
        try:
            username, password = self._vault.get(token)
            raw = self._runner.fetch_activities(username=username, password=password, since=since)
            return [self._normalize(a) for a in raw]
        finally:
            # Destroy credentials immediately after use.
            self._vault.delete(token)

    def get_profile(self, user_id: str) -> Dict:
        token = self._vault.token_for_user(user_id)
        if token is None:
            return {}
        try:
            username, password = self._vault.get(token)
            return self._runner.get_profile(username=username, password=password)
        finally:
            self._vault.delete(token)

    def get_daily_metrics(self, user_id: str, days: int = 7) -> List[Dict]:
        token = self._vault.token_for_user(user_id)
        if token is None:
            raise GccliError("No active Garmin session for user")
        try:
            username, password = self._vault.get(token)
            raw = self._runner.fetch_daily_metrics(username=username, password=password, days=days)
            return [self._normalize_metric(m) for m in raw]
        finally:
            self._vault.delete(token)

    @staticmethod
    def _normalize(raw: Dict) -> Dict:
        return {
            "external_id": raw.get("id") or raw.get("activityId"),
            "source": "garmin",
            "name": raw.get("name") or raw.get("activityName"),
            "activity_type": raw.get("type") or raw.get("activityType"),
            "start_time": raw.get("start_time") or raw.get("startTimeLocal"),
            "distance": raw.get("distance_m") or raw.get("distance"),
            "duration": raw.get("duration_s") or raw.get("duration"),
            "avg_hr": raw.get("avg_hr") or raw.get("averageHR"),
            "pace": raw.get("avg_pace") or raw.get("pace"),
            "raw_payload": raw,
        }

    @staticmethod
    def _normalize_metric(raw: Dict) -> Dict:
        return {
            "date": raw.get("date") or raw.get("calendarDate"),
            "hrv": raw.get("hrv") or raw.get("hrvWeeklyAvg") or raw.get("avgHrv"),
            "resting_hr": raw.get("resting_hr") or raw.get("restingHeartRate"),
            "sleep_hours": raw.get("sleep_hours")
            or (raw.get("sleepTimeSeconds", 0) / 3600 if raw.get("sleepTimeSeconds") else None),
            "sleep_score": raw.get("sleep_score") or raw.get("sleepScore"),
            "source": "garmin",
        }
