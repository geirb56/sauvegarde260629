"""MockProvider — full, credential-free Garmin connector for the MVP.

Produces deterministic, normalized activities so the entire connect -> sync ->
store flow works end-to-end without any real Garmin account and without ever
collecting a password. Also supports an optional MFA simulation so the
'mfa_required' (Mode 2) code path can be exercised by tests.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .base import (
    ConnectResult,
    Provider,
    STATUS_CONNECTED,
    STATUS_MFA_REQUIRED,
)

_ACTIVITY_TYPES = [
    ("Morning Run", "running"),
    ("Easy Run", "running"),
    ("Tempo Run", "running"),
    ("Long Run", "running"),
    ("Recovery Run", "running"),
    ("Interval Session", "running"),
    ("Bike Ride", "cycling"),
    ("Trail Run", "trail_running"),
]


def _format_pace(seconds_per_km: float) -> str:
    minutes = int(seconds_per_km // 60)
    seconds = int(round(seconds_per_km % 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


class MockProvider(Provider):
    name = "mock"

    def __init__(self) -> None:
        # Tracks one-time MFA challenges per user (in-memory, ephemeral).
        self._pending_mfa: set[str] = set()

    def connect(self, user_id: str, simulate_mfa: bool = False) -> ConnectResult:
        # Mode 2 (MFA) simulation: first call returns mfa_required, a retry succeeds.
        if simulate_mfa and user_id not in self._pending_mfa:
            self._pending_mfa.add(user_id)
            return ConnectResult(
                status=STATUS_MFA_REQUIRED,
                detail="Additional Garmin verification required. Please retry the connection.",
            )
        self._pending_mfa.discard(user_id)
        return ConnectResult(status=STATUS_CONNECTED, detail="Garmin connected")

    def _seed(self, user_id: str) -> int:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def sync_activities(self, user_id: str, since: Optional[str] = None) -> List[Dict]:
        rng = random.Random(self._seed(user_id))
        now = datetime.now(timezone.utc)
        count = rng.randint(6, 9)
        activities: List[Dict] = []
        for i in range(count):
            name, atype = rng.choice(_ACTIVITY_TYPES)
            distance_km = round(rng.uniform(4.0, 22.0), 2)
            distance_m = round(distance_km * 1000)
            pace_spk = rng.uniform(270, 390)  # 4:30 - 6:30 /km
            duration_s = int(distance_km * pace_spk)
            avg_hr = rng.randint(128, 172)
            start_time = (now - timedelta(days=i, hours=rng.randint(0, 6))).replace(microsecond=0)
            activities.append(
                {
                    "external_id": f"mock-{user_id}-{i}",
                    "source": "garmin",
                    "name": name,
                    "activity_type": atype,
                    "start_time": start_time.isoformat(),
                    "distance": distance_m,
                    "duration": duration_s,
                    "avg_hr": avg_hr,
                    "pace": _format_pace(pace_spk),
                    "pace_seconds_per_km": round(pace_spk, 1),
                    "raw_payload": {
                        "id": f"mock-{user_id}-{i}",
                        "distance_m": distance_m,
                        "duration_s": duration_s,
                        "avg_hr": avg_hr,
                    },
                }
            )
        return activities

    def get_profile(self, user_id: str) -> Dict:
        return {
            "source": "garmin",
            "display_name": "Mock Athlete",
            "connected": True,
        }

    def get_daily_metrics(self, user_id: str, days: int = 7) -> List[Dict]:
        rng = random.Random(self._seed(user_id) + 7919)
        now = datetime.now(timezone.utc)
        # Stable per-user baselines
        base_hrv = rng.randint(48, 78)
        base_rhr = rng.randint(42, 56)
        metrics: List[Dict] = []
        for i in range(days):
            day = (now - timedelta(days=i)).date().isoformat()
            hrv = max(20, base_hrv + rng.randint(-12, 12))
            resting_hr = max(35, base_rhr + rng.randint(-4, 6))
            sleep_hours = round(rng.uniform(5.5, 8.7), 1)
            sleep_score = rng.randint(55, 95)
            metrics.append(
                {
                    "date": day,
                    "hrv": hrv,
                    "resting_hr": resting_hr,
                    "sleep_hours": sleep_hours,
                    "sleep_score": sleep_score,
                    "source": "garmin",
                }
            )
        return metrics
