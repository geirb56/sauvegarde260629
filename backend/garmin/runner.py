"""GccliRunner — isolated wrapper around the `gccli` binary.

This is the ONLY place that knows how to talk to Garmin Connect through the
gccli command-line tool. It is intentionally isolated so that the rest of the
application never depends on gccli details.

If the gccli binary is not installed, or Garmin requires interactive auth that
is incompatible with the invisible product flow, methods raise
`GccliUnavailable`. Callers (the provider/service) are expected to handle this
gracefully (e.g. surface an 'mfa_required'/reconnect state).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from time import sleep
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GccliError(Exception):
    """Generic gccli failure."""


class GccliUnavailable(GccliError):
    """Raised when the gccli binary is missing or auth is interactive."""


class GccliRunner:
    def __init__(self, gccli_path: str = "gccli", timeout_seconds: int = 30, max_retries: int = 3):
        self.gccli_path = gccli_path
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return shutil.which(self.gccli_path) is not None

    def _ensure_available(self) -> None:
        if not self.is_available():
            raise GccliUnavailable(
                f"gccli binary '{self.gccli_path}' not found in PATH"
            )

    def _run_cmd(self, args: List[str], env=None) -> subprocess.CompletedProcess:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return subprocess.run(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout,
                    check=True,
                    env=env,
                )
            except subprocess.CalledProcessError as e:
                last_exc = e
                logger.warning("gccli failed (attempt %d/%d)", attempt, self.max_retries)
                if attempt < self.max_retries:
                    sleep(attempt)
                    continue
                raise GccliError("gccli call failed") from e
            except subprocess.TimeoutExpired as e:
                last_exc = e
                logger.warning("gccli timed out (attempt %d/%d)", attempt, self.max_retries)
                if attempt < self.max_retries:
                    continue
                raise GccliError("gccli timed out") from e
        raise last_exc or GccliError("gccli unknown error")

    def login(self, username: str, password: str, workdir: str) -> None:
        self._ensure_available()
        cmd = [self.gccli_path, "auth", "login", username, "--headless", "--password-stdin"]
        pfile = None
        try:
            pfile = tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=workdir)
            pfile.write(password)
            pfile.flush()
            os.fchmod(pfile.fileno(), 0o600)
            pfile.close()
            cmd = [self.gccli_path, "auth", "login", username, "--headless", "--password-file", pfile.name]
            self._run_cmd(cmd, env=os.environ.copy())
        finally:
            if pfile:
                try:
                    os.remove(pfile.name)
                except OSError:
                    logger.exception("failed to remove temp password file")

    def fetch_activities(self, username: str, password: str, since: Optional[str] = None) -> List[Dict]:
        self._ensure_available()
        tmpdir = tempfile.mkdtemp(prefix="gccli-")
        try:
            self.login(username, password, workdir=tmpdir)
            cmd = [self.gccli_path, "activities", "list", "--output", "json"]
            if since:
                cmd += ["--start-date", since]
            cp = self._run_cmd(cmd, env=os.environ.copy())
            return json.loads(cp.stdout.decode("utf-8"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def get_profile(self, username: str, password: str) -> Dict:
        self._ensure_available()
        tmpdir = tempfile.mkdtemp(prefix="gccli-")
        try:
            self.login(username, password, workdir=tmpdir)
            cp = self._run_cmd([self.gccli_path, "profile", "get", "--output", "json"], env=os.environ.copy())
            return json.loads(cp.stdout.decode("utf-8"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def fetch_daily_metrics(self, username: str, password: str, days: int = 7) -> List[Dict]:
        """Fetch recent daily health stats (HRV, resting HR, sleep) via gccli."""
        self._ensure_available()
        tmpdir = tempfile.mkdtemp(prefix="gccli-")
        try:
            self.login(username, password, workdir=tmpdir)
            cmd = [self.gccli_path, "health", "daily", "--days", str(days), "--output", "json"]
            cp = self._run_cmd(cmd, env=os.environ.copy())
            data = json.loads(cp.stdout.decode("utf-8"))
            return data if isinstance(data, list) else data.get("days", [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
