"""Garmin sync job queue — enqueue side (used by the FastAPI process).

All Garmin sync work is enqueued here and executed out-of-process by
workers/sync_worker.py. The API never runs blocking gccli calls itself.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid

from .redis_client import get_redis

logger = logging.getLogger(__name__)

# Single FIFO queue (LPUSH to enqueue, BLMOVE to claim into processing).
QUEUE_KEY = "cardiocoach:garmin:queue"
# Reliable-queue in-flight list: a job lives here from claim until ACK.
PROCESSING_KEY = "cardiocoach:garmin:processing"
# Hash job_id -> claimed_at (epoch); used by the watchdog to detect orphans.
CLAIMS_KEY = "cardiocoach:garmin:claims"
# A job stuck in processing longer than this (s) is considered orphaned.
ORPHAN_TIMEOUT = int(os.environ.get("SYNC_ORPHAN_TIMEOUT", "120"))

# Job types
JOB_SYNC_USER = "SYNC_USER"          # full sync: activities + daily health metrics
JOB_SYNC_ACTIVITY = "SYNC_ACTIVITY"  # activities-focused sync

# Redis keys for throttling / dedupe
LOCK_PREFIX = "sync_lock:"       # per-user concurrency lock (worker side)
LOCK_TTL = 120                   # seconds
PENDING_PREFIX = "sync_pending:"  # dedupe flag: a job is queued/running for user
PENDING_TTL = 300                # seconds


async def _push(job_type: str, user_id: str, attempts: int = 0, job_id: str = None) -> None:
    r = get_redis()
    payload = json.dumps({
        "id": job_id or uuid.uuid4().hex,
        "type": job_type,
        "user_id": user_id,
        "attempts": attempts,
        "enqueued_at": time.time(),
    })
    await r.lpush(QUEUE_KEY, payload)


async def _enqueue_deduped(job_type: str, user_id: str) -> dict:
    """Enqueue a job, skipping if one is already pending for this user."""
    r = get_redis()
    # NX pending flag prevents flooding the queue with duplicates for one user.
    fresh = await r.set(f"{PENDING_PREFIX}{user_id}", job_type, nx=True, ex=PENDING_TTL)
    if not fresh:
        logger.info("[queue] job=%s already pending user=%s (skipped)", job_type, user_id)
        return {"status": "already_queued"}
    await _push(job_type, user_id)
    logger.info("[queue] enqueued job=%s user=%s", job_type, user_id)
    return {"status": "queued"}


async def enqueue_sync(user_id: str) -> dict:
    """Queue a full user sync (activities + daily metrics)."""
    return await _enqueue_deduped(JOB_SYNC_USER, user_id)


async def enqueue_activity_sync(user_id: str) -> dict:
    """Queue an activities-focused sync."""
    return await _enqueue_deduped(JOB_SYNC_ACTIVITY, user_id)
