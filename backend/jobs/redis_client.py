"""Shared async Redis connection (lazy singleton, per-process)."""

from __future__ import annotations

import os

import redis.asyncio as aioredis

_redis: "aioredis.Redis | None" = None


def get_redis() -> "aioredis.Redis":
    global _redis
    if _redis is None:
        url = os.environ["REDIS_URL"]
        _redis = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
    return _redis
