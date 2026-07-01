"""Garmin sync worker — consumes the Redis queue out-of-process.

Runs independently from the FastAPI process (own event loop, own Mongo + Redis
connections). Responsibilities:
  - consume the job queue (BRPOP)
  - execute the real gccli sync via the existing service/provider layer
  - throttle: max N concurrent syncs, one active sync per user (Redis lock)
  - retries (max SYNC_MAX_RETRIES) with backoff
  - per-job timeout (SYNC_JOB_TIMEOUT seconds)
  - structured logs (never credentials)

Start with:  python -m workers.sync_worker   (cwd = /app/backend)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time

# Make /app/backend importable when launched as a module or script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()  # load backend/.env when run standalone

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient

from jobs.queue import (
    QUEUE_KEY,
    JOB_SYNC_USER,
    JOB_SYNC_ACTIVITY,
    LOCK_PREFIX,
    LOCK_TTL,
    PENDING_PREFIX,
)
from garmin import service as garmin_service
from garmin.bootstrap import ensure_gccli_installed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sync_worker")

MAX_CONCURRENCY = int(os.environ.get("SYNC_MAX_CONCURRENCY", "5"))
JOB_TIMEOUT = int(os.environ.get("SYNC_JOB_TIMEOUT", "60"))
MAX_RETRIES = int(os.environ.get("SYNC_MAX_RETRIES", "3"))
# Periodic auto-sync (0 = disabled). When >0, all connected users are enqueued
# every N seconds, staggered to avoid a thundering herd at 1k users.
SCHEDULE_INTERVAL = int(os.environ.get("SYNC_SCHEDULE_INTERVAL", "0"))
SCHEDULE_STAGGER_MS = int(os.environ.get("SYNC_SCHEDULE_STAGGER_MS", "200"))


async def _run_job(db, job_type: str, user_id: str) -> dict:
    if job_type in (JOB_SYNC_USER, JOB_SYNC_ACTIVITY):
        # service.sync is idempotent (upserts) and writes to Mongo.
        return await garmin_service.sync(db, user_id)
    raise ValueError(f"unknown job type: {job_type}")


async def process_job(db, redis, raw: str) -> None:
    try:
        job = json.loads(raw)
    except (ValueError, TypeError):
        logger.error("[worker] dropped malformed job payload")
        return

    job_type = job.get("type")
    user_id = job.get("user_id")
    attempts = int(job.get("attempts", 0))
    lock_key = f"{LOCK_PREFIX}{user_id}"

    # One active sync per user.
    if not await redis.set(lock_key, "1", nx=True, ex=LOCK_TTL):
        logger.info("[worker] user=%s already syncing -> requeue", user_id)
        await asyncio.sleep(1)
        await redis.lpush(QUEUE_KEY, raw)  # back of the FIFO queue
        return

    start = time.time()
    logger.info("[worker] sync_start type=%s user=%s attempt=%s", job_type, user_id, attempts + 1)
    try:
        result = await asyncio.wait_for(_run_job(db, job_type, user_id), timeout=JOB_TIMEOUT)
        duration = round(time.time() - start, 2)
        logger.info(
            "[worker] sync_success type=%s user=%s duration=%ss synced=%s metrics=%s",
            job_type, user_id, duration,
            result.get("synced_count"), result.get("metrics_count"),
        )
        await redis.delete(f"{PENDING_PREFIX}{user_id}")
    except Exception as exc:  # timeout or provider/runner failure
        duration = round(time.time() - start, 2)
        attempts += 1
        if attempts < MAX_RETRIES:
            backoff = min(5 * attempts, 15)
            logger.warning(
                "[worker] sync_retry type=%s user=%s attempt=%s duration=%ss backoff=%ss err=%s",
                job_type, user_id, attempts, duration, backoff, exc,
            )
            job["attempts"] = attempts
            await asyncio.sleep(backoff)
            await redis.lpush(QUEUE_KEY, json.dumps(job))
        else:
            logger.error(
                "[worker] sync_failed type=%s user=%s attempts=%s duration=%ss err=%s",
                job_type, user_id, attempts, duration, exc,
            )
            await redis.delete(f"{PENDING_PREFIX}{user_id}")
    finally:
        await redis.delete(lock_key)


async def scheduler_loop(db) -> None:
    """Optionally enqueue a sync for every connected user on a fixed interval.

    Disabled unless SYNC_SCHEDULE_INTERVAL > 0. Enqueues are deduped and
    staggered so 1k users don't hit Garmin simultaneously.
    """
    from jobs.queue import enqueue_sync  # local import: uses this process's Redis

    logger.info("[scheduler] enabled interval=%ss stagger=%sms", SCHEDULE_INTERVAL, SCHEDULE_STAGGER_MS)
    while True:
        try:
            cursor = db.garmin_connections.find({"connected": True}, {"_id": 0, "user_id": 1})
            count = 0
            async for conn in cursor:
                uid = conn.get("user_id")
                if not uid:
                    continue
                await enqueue_sync(uid)
                count += 1
                if SCHEDULE_STAGGER_MS:
                    await asyncio.sleep(SCHEDULE_STAGGER_MS / 1000.0)
            logger.info("[scheduler] tick enqueued=%s connected users", count)
        except Exception as exc:
            logger.error("[scheduler] error: %s", exc)
        await asyncio.sleep(SCHEDULE_INTERVAL)


async def main() -> None:
    # Ensure the gccli binary is on PATH for this (separate) worker process.
    try:
        ensure_gccli_installed()
    except Exception as exc:  # best-effort, never blocks worker startup
        logger.warning("[worker] gccli bootstrap skipped: %s", exc)

    # socket_timeout=None so blocking BRPOP is not cut short by the client.
    redis = aioredis.from_url(
        os.environ["REDIS_URL"],
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=None,
        socket_connect_timeout=5,
        health_check_interval=30,
    )
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    logger.info(
        "[worker] started concurrency=%s job_timeout=%ss max_retries=%s queue=%s",
        MAX_CONCURRENCY, JOB_TIMEOUT, MAX_RETRIES, QUEUE_KEY,
    )

    if SCHEDULE_INTERVAL > 0:
        asyncio.create_task(scheduler_loop(db))

    while True:
        try:
            await sem.acquire()
            item = await redis.brpop(QUEUE_KEY, timeout=5)
            if not item:
                sem.release()
                continue
            _key, raw = item
            task = asyncio.create_task(process_job(db, redis, raw))
            task.add_done_callback(lambda _t: sem.release())
        except asyncio.CancelledError:
            break
        except Exception as exc:  # keep the loop alive
            logger.error("[worker] loop error: %s", exc)
            try:
                sem.release()
            except ValueError:
                pass
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
