"""Garmin orchestration service.

Coordinates the provider with MongoDB persistence. Stores ONLY normalized
business data (connection status + activities). Never stores credentials.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .factory import get_provider, active_provider_name
from .providers.base import STATUS_CONNECTED, STATUS_MFA_REQUIRED

logger = logging.getLogger(__name__)


async def connect(db, user_id: str, simulate_mfa: bool = False) -> dict:
    provider = get_provider()
    result = provider.connect(user_id, simulate_mfa=simulate_mfa)

    if result.status == STATUS_CONNECTED:
        await db.garmin_connections.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "connected": True,
                "provider": active_provider_name(),
                "connected_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        logger.info("[Garmin] connected user=%s provider=%s", user_id, active_provider_name())

    return {"status": result.status, "message": result.detail, "provider": active_provider_name()}


async def sync(db, user_id: str, since: Optional[str] = None) -> dict:
    conn = await db.garmin_connections.find_one({"user_id": user_id}, {"_id": 0})
    if not conn or not conn.get("connected"):
        return {"success": False, "synced_count": 0, "message": "Garmin not connected"}

    provider = get_provider()
    try:
        activities = provider.sync_activities(user_id, since=since)
    except Exception as exc:  # provider/runner failures -> graceful
        logger.error("[Garmin] sync failed user=%s: %s", user_id, exc)
        return {"success": False, "synced_count": 0, "message": "Sync failed, please reconnect"}

    synced = 0
    for act in activities:
        ext_id = act.get("external_id")
        if not ext_id:
            continue
        doc = {**act, "user_id": user_id, "synced_at": datetime.now(timezone.utc).isoformat()}
        await db.garmin_activities.update_one(
            {"user_id": user_id, "external_id": ext_id},
            {"$set": doc},
            upsert=True,
        )
        synced += 1

    total = await db.garmin_activities.count_documents({"user_id": user_id})
    await db.garmin_connections.update_one(
        {"user_id": user_id},
        {"$set": {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "activity_count": total,
        }},
    )
    logger.info("[Garmin] synced %d activities user=%s", synced, user_id)
    return {"success": True, "synced_count": synced, "message": f"Imported {synced} activities"}


async def get_status(db, user_id: str) -> dict:
    conn = await db.garmin_connections.find_one({"user_id": user_id}, {"_id": 0})
    if not conn:
        return {
            "connected": False,
            "provider": active_provider_name(),
            "last_sync": None,
            "activity_count": 0,
        }
    return {
        "connected": bool(conn.get("connected")),
        "provider": conn.get("provider", active_provider_name()),
        "last_sync": conn.get("last_sync"),
        "activity_count": conn.get("activity_count", 0),
    }


async def disconnect(db, user_id: str) -> dict:
    await db.garmin_connections.delete_one({"user_id": user_id})
    await db.garmin_activities.delete_many({"user_id": user_id})
    logger.info("[Garmin] disconnected user=%s", user_id)
    return {"success": True, "message": "Garmin disconnected"}


async def list_activities(db, user_id: str, limit: int = 20) -> list:
    cursor = (
        db.garmin_activities.find({"user_id": user_id}, {"_id": 0})
        .sort("start_time", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
