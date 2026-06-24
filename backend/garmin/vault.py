"""EphemeralCredentialVault — in-memory, short-lived credential storage.

Design constraints (non-negotiable):
- Credentials live ONLY in process memory, never on disk, never in MongoDB,
  never in the repo, never logged.
- Short TTL. Credentials are destroyed immediately after a sync completes.
- Values are encrypted at rest in memory with AES-GCM so they are not
  trivially readable from a heap dump.

This vault is used exclusively by the GccliProvider for the (dev-only) real
path. The MockProvider never touches it.
"""

from __future__ import annotations

import base64
import os
import secrets
import time
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_TTL = 300  # 5 minutes — credentials are transient by design


class EphemeralCredentialVault:
    """Encrypted, in-memory credential store with TTL."""

    def __init__(self, master_key_b64: Optional[str] = None, default_ttl: int = DEFAULT_TTL):
        # If no master key provided, generate a random one for this process only.
        # Since the vault is in-memory and never persisted, an ephemeral key is fine.
        if master_key_b64:
            key = base64.b64decode(master_key_b64)
        else:
            key = AESGCM.generate_key(bit_length=256)
        self._aesgcm = AESGCM(key)
        self._default_ttl = default_ttl
        self._store: dict[str, dict] = {}

    def _encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, b"")
        return nonce + ciphertext

    def _decrypt(self, blob: bytes) -> bytes:
        nonce, ct = blob[:12], blob[12:]
        return self._aesgcm.decrypt(nonce, ct, b"")

    def store(self, user_id: str, username: str, password: str, ttl: Optional[int] = None) -> str:
        """Store credentials transiently. Returns an opaque session token."""
        token = secrets.token_urlsafe(32)
        payload = f"{username}\n{password}".encode("utf-8")
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[token] = {
            "blob": self._encrypt(payload),
            "user_id": user_id,
            "expires_at": expires_at,
        }
        return token

    def get(self, token: str) -> Tuple[str, str]:
        rec = self._store.get(token)
        if not rec or rec["expires_at"] < time.time():
            self._store.pop(token, None)
            raise KeyError("credentials not found or expired")
        plaintext = self._decrypt(rec["blob"]).decode("utf-8")
        username, password = plaintext.split("\n", 1)
        return username, password

    def delete(self, token: str) -> None:
        self._store.pop(token, None)

    def token_for_user(self, user_id: str) -> Optional[str]:
        now = time.time()
        for token, rec in list(self._store.items()):
            if rec["expires_at"] < now:
                self._store.pop(token, None)
                continue
            if rec["user_id"] == user_id:
                return token
        return None
