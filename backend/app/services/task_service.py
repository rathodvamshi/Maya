from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

from bson import ObjectId

from app.database import db_client
from app.services.redis_service import get_client as get_redis
from app.utils import email_utils

logger = logging.getLogger(__name__)


def _naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    try:
        return dt.replace(tzinfo=None)
    except Exception:
        return dt


def _window(due: datetime, seconds: int = 300) -> tuple[datetime, datetime]:
    return (due - timedelta(seconds=seconds), due + timedelta(seconds=seconds))


def _user_id_str(current_user: Dict[str, Any]) -> str:
    return str(current_user.get("user_id") or current_user.get("_id") or current_user.get("id"))


def _safe_object_id(val: str | ObjectId) -> Any:
    try:
        return ObjectId(val)
    except Exception:
        return val


def create_task(user, title: str, due_date_utc: datetime, description: str = None, priority: str = "normal", auto_complete: bool = True) -> str:
    """
    Create task + schedule Celery as specified in requirements.
    Returns task_id string.
    """
    from bson import ObjectId
    
    coll = db_client.get_tasks_collection()
    if not db_client.healthy():
        raise RuntimeError("Database unavailable")

    now = datetime.utcnow()
    user_id = _user_id_str(user)
    
    # Create task document
    task_doc = {
        "user_id": user_id,
        "title": title,
        "description": description or "",
        "due_date": due_date_utc,
        "priority": priority,
        "status": "todo",
        "auto_complete_after_email": auto_complete,
        "created_at": now,
        "updated_at": now,
        "celery_task_id": None,
        "tags": [],
        "recurrence": "none",
        "notify_channel": "email",
        "metadata": {}
    }
    
    res = coll.insert_one(task_doc)
    task_id = str(res.inserted_id)

    # Schedule Celery job
    try:
        from app.celery_worker import send_task_otp_task
        user_email = user.get("email") or user.get("user_email")
        if user_email:
            async_res = send_task_otp_task.apply_async(args=[task_id, user_email, title], eta=due_date_utc)
            coll.update_one({"_id": ObjectId(task_id)}, {"$set": {"celery_task_id": async_res.id}})
            logger.info(f"[TASK_CREATED] Task={title}, task_id={task_id}, due_utc={due_date_utc.isoformat()}Z, user_id={user_id}")
            logger.info(f"[OTP_SCHEDULED] CeleryId={async_res.id}, ETA={due_date_utc.isoformat()}Z")
    except Exception as e:
        logger.warning(f"Failed to schedule OTP task: {e}")

    return task_id


def create_task_legacy(current_user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Legacy create_task function for backward compatibility.
    """
    coll = db_client.get_tasks_collection()
    if not db_client.healthy():
        raise RuntimeError("Database unavailable")

    now = datetime.utcnow()
    user_id = _user_id_str(current_user)
    title = (payload.get("title") or "").strip()
    due = _naive(payload.get("due_date"))
    if due is None:
        raise ValueError("due_date required")
    if due <= now and not payload.get("allow_past", False):
        raise ValueError("due_date must be in the future")

    # Duplicate within ±5 minutes
    ws, we = _window(due, 300)
    existing = coll.find_one({
        "user_id": user_id,
        "title": title,
        "due_date": {"$gte": ws, "$lte": we},
    })
    if existing:
        raise ValueError("duplicate_task_window")

    doc = {
        "_id": str(ObjectId()),
        "user_id": user_id,
        "title": title,
        "description": (payload.get("description") or "").strip(),
        "status": payload.get("status") or "todo",
        "priority": payload.get("priority") or "medium",
        "due_date": due,
        "tags": payload.get("tags") or [],
        "recurrence": payload.get("recurrence") or "none",
        "notify_channel": payload.get("notify_channel") or "email",
        "auto_complete_after_email": payload.get("auto_complete_after_email", True),
        "created_at": now,
        "updated_at": now,
        "celery_task_id": None,
        "metadata": {},
    }
    coll.insert_one(doc)

    # Schedule OTP email at exact due time
    try:
        from app.celery_worker import send_task_otp_task
        user_email = current_user.get("email") or current_user.get("user_email")
        if user_email:
            res = send_task_otp_task.apply_async(args=[str(doc["_id"]), user_email, title], eta=due)
            try:
                coll.update_one({"_id": doc["_id"]}, {"$set": {"celery_task_id": res.id}})
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Failed to schedule OTP task: {e}")

    return doc


def reschedule_task(current_user: Dict[str, Any], task_id: str, new_due_date: datetime) -> Dict[str, Any]:
    coll = db_client.get_tasks_collection()
    user_id = _user_id_str(current_user)
    doc = coll.find_one({"_id": _safe_object_id(task_id), "user_id": user_id})
    if not doc:
        raise ValueError("not_found")
    old_celery = doc.get("celery_task_id")
    # Best-effort revoke if we had a celery id
    if old_celery:
        try:
            from app.celery_app import celery_app
            celery_app.control.revoke(old_celery, terminate=False)
        except Exception:
            pass
    now = datetime.utcnow()
    coll.update_one({"_id": doc["_id"]}, {"$set": {"due_date": _naive(new_due_date), "updated_at": now}})
    # Re-schedule
    try:
        from app.celery_worker import send_task_otp_task
        user_email = current_user.get("email") or current_user.get("user_email")
        if user_email:
            res = send_task_otp_task.apply_async(args=[user_id, user_email, str(doc["_id"]), doc.get("title") or "Reminder"], eta=_naive(new_due_date))
            coll.update_one({"_id": doc["_id"]}, {"$set": {"celery_task_id": res.id}})
    except Exception:
        pass
    return coll.find_one({"_id": doc["_id"]}) or {}


def delete_task(current_user: Dict[str, Any], task_id: str) -> bool:
    coll = db_client.get_tasks_collection()
    user_id = _user_id_str(current_user)
    doc = coll.find_one({"_id": _safe_object_id(task_id), "user_id": user_id})
    if not doc:
        return False
    if doc.get("celery_task_id"):
        try:
            from app.celery_app import celery_app
            celery_app.control.revoke(doc["celery_task_id"], terminate=False)
        except Exception:
            pass
    res = coll.delete_one({"_id": doc["_id"]})
    return bool(getattr(res, "deleted_count", 0))


def verify_otp(current_user: Dict[str, Any], task_id: str, otp: str) -> Dict[str, Any]:
    client = get_redis()
    if not client:
        raise RuntimeError("redis_unavailable")
    key = f"otp:task:{task_id}"
    try:
        # asyncio Redis client supports await, but we may run in sync context here
        # use .get via loop if available. Fallback to blocking call if configured so.
        import asyncio
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and hasattr(client, "get"):
            val = loop.run_until_complete(client.get(key))  # type: ignore[attr-defined]
        else:
            val = None
    except Exception:
        val = None

    # Fallback to direct await if within async call contexts
    if val is None:
        try:
            import asyncio
            val = asyncio.get_event_loop().run_until_complete(client.get(key))  # type: ignore[attr-defined]
        except Exception:
            val = None

    if not val:
        return {"verified": False, "reason": "otp_expired_or_missing"}
    if str(val).strip() != str(otp).strip():
        return {"verified": False, "reason": "otp_mismatch"}

    try:
        # delete otp
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.delete(key))  # type: ignore[attr-defined]
    except Exception:
        pass

    # Mark task metadata
    coll = db_client.get_tasks_collection()
    coll.update_one({"_id": _safe_object_id(task_id), "user_id": _user_id_str(current_user)}, {"$set": {"metadata.otp_verified": True, "updated_at": datetime.utcnow()}})
    return {"verified": True}


def list_upcoming_summary(current_user: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    coll = db_client.get_tasks_collection()
    user_id = _user_id_str(current_user)
    now = datetime.utcnow()
    cur = coll.find({"user_id": user_id, "due_date": {"$gte": now}, "status": {"$in": ["todo", "in_progress"]}}).sort("due_date", 1).limit(int(limit))
    out: List[Dict[str, Any]] = []
    for d in cur:
        dd = dict(d)
        try:
            dd["_id"] = str(dd.get("_id"))
        except Exception:
            pass
        out.append(dd)
    return out


