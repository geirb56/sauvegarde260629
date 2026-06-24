"""Provider factory — selects the active Garmin provider via env.

GARMIN_PROVIDER = mock (default) | gccli

Returns process-level singletons so in-memory state (mock MFA challenges,
ephemeral vault sessions) is shared across requests.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .providers.base import Provider
from .providers.mock_provider import MockProvider
from .providers.gccli_provider import GccliProvider
from .runner import GccliRunner
from .vault import EphemeralCredentialVault


@lru_cache(maxsize=1)
def _mock_provider() -> MockProvider:
    return MockProvider()


@lru_cache(maxsize=1)
def _gccli_provider() -> GccliProvider:
    vault = EphemeralCredentialVault(master_key_b64=os.environ.get("GARMIN_VAULT_KEY"))
    runner = GccliRunner(gccli_path=os.environ.get("GCCLI_PATH", "gccli"))
    return GccliProvider(vault=vault, runner=runner)


def get_provider() -> Provider:
    name = os.environ.get("GARMIN_PROVIDER", "mock").strip().lower()
    if name == "gccli":
        return _gccli_provider()
    return _mock_provider()


def active_provider_name() -> str:
    return os.environ.get("GARMIN_PROVIDER", "mock").strip().lower()
