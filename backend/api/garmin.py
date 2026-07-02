"""Garmin API router (HTTP layer).

Prefix /api is added when included by server.py (api_router has prefix /api).
Final routes: /api/garmin/*

NON-NEGOTIABLE: no Garmin password is ever accepted from the client.
The connect endpoint takes only a user_id (auth abstracted backend-side).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from garmin import service as garmin_service
from jobs.queue import enqueue_sync
from jobs.health import queue_health

import logging
logger = logging.getLogger(__name__)

garmin_router = APIRouter(prefix="/garmin", tags=["garmin"])


async def _safe_enqueue(user_id: str):
    """Enqueue a sync, tolerating a transient Redis outage."""
    try:
        return await enqueue_sync(user_id), None
    except Exception as exc:  # Redis down / connection error
        logger.error("[garmin] enqueue failed for user=%s: %s", user_id, exc)
        return None, exc


class GarminConnectRequest(BaseModel):
    # Optional, testing-only hook to exercise the MFA (Mode 2) code path.
    simulate_mfa: bool = False


@garmin_router.post("/connect")
async def connect_garmin(request: Request, body: Optional[GarminConnectRequest] = None, user_id: str = "default"):
    """Establish the Garmin session (fast auth check) and queue the initial sync.

    Auth is a lightweight token/status check (non-blocking); the heavy activity
    + metrics fetch is offloaded to the worker so the request returns instantly.
    """
    db = request.app.state.db
    simulate_mfa = bool(body.simulate_mfa) if body else False
    result = await garmin_service.connect(db, user_id, simulate_mfa=simulate_mfa)
    if result.get("status") == "connected":
        # Kick off the first data sync in the background (never blocks the API).
        # Redis outage must not fail the connect itself.
        await _safe_enqueue(user_id)
    return result


@garmin_router.post("/sync")
async def sync_garmin(request: Request, user_id: str = "default"):
    """Non-blocking: enqueue a Garmin sync job and return immediately."""
    res, err = await _safe_enqueue(user_id)
    if err is not None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "sync service temporarily unavailable, retry shortly"},
        )
    return res


@garmin_router.get("/status")
async def garmin_status(request: Request, user_id: str = "default"):
    db = request.app.state.db
    return await garmin_service.get_status(db, user_id)


@garmin_router.get("/queue/health")
async def garmin_queue_health():
    """Lightweight, READ-ONLY Redis health snapshot of the sync queue.

    Response JSON:
      status                     "healthy" | "degraded" | "unhealthy"
      redis_connected            bool
      queue_length               int  — jobs waiting to be claimed
      processing_length          int  — jobs currently in-flight
      active_workers             int  — live worker heartbeats
      oldest_processing_seconds  int  — age of the oldest in-flight job (0 if none)
      orphans_recovered_total    int  — cumulative jobs requeued by the watchdog
      failed_jobs_total          int  — cumulative jobs that failed after max retries
      timestamp                  str  — ISO-8601 UTC

    Status rules: UNHEALTHY if redis down OR active_workers==0 OR
    oldest_processing>=120s OR queue_length>=2000; DEGRADED if queue_length>=500
    OR oldest_processing>=96s; otherwise HEALTHY.
    """
    return await queue_health()


@garmin_router.post("/disconnect")
async def disconnect_garmin(request: Request, user_id: str = "default"):
    db = request.app.state.db
    return await garmin_service.disconnect(db, user_id)


@garmin_router.get("/activities")
async def garmin_activities(request: Request, user_id: str = "default", limit: int = 20):
    db = request.app.state.db
    items = await garmin_service.list_activities(db, user_id, limit=limit)
    return {"activities": items, "count": len(items)}


@garmin_router.get("/daily-metrics")
async def garmin_daily_metrics(request: Request, user_id: str = "default", days: int = 7):
    db = request.app.state.db
    return await garmin_service.get_daily_metrics(db, user_id, days=days)
