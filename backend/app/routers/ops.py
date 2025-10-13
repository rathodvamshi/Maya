from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from pymongo.collection import Collection

from app.database import get_tasks_collection, db_client
from app.security import get_current_active_user
from app.celery_worker import celery_app

router = APIRouter(prefix="/api/ops", tags=["Ops"], dependencies=[Depends(get_current_active_user)])


@router.get("/list_scheduled_tasks")
async def list_scheduled_tasks(current_user: dict = Depends(get_current_active_user),
                               tasks_collection: Collection = Depends(get_tasks_collection)):
    """Return upcoming reminders for the current user sorted by due_date ascending."""
    now = datetime.utcnow()
    cursor = tasks_collection.find({
        "user_id": current_user["user_id"],
        "status": {"$in": ["todo", "pending", "in_progress"]},
        "due_date": {"$gte": now},
    }).sort("due_date", 1).limit(200)
    items = []
    for doc in cursor:
        items.append({
            "task_id": str(doc.get("_id")),
            "title": doc.get("title"),
            "due_date": doc.get("due_date"),
            "status": doc.get("status"),
            "celery_task_id": doc.get("celery_task_id"),
            "attempts": doc.get("attempts", 0),
            "last_error": doc.get("last_error"),
        })
    return items


@router.get("/celery_health_check")
async def celery_health_check():
    """Check broker connectivity. SMTP checks removed."""
    out = {"broker_ok": False, "details": {}}
    try:
        insp = celery_app.control.inspect(timeout=2.0)
        ping = insp.ping() or {}
        out["details"]["inspect_ping"] = ping
        out["broker_ok"] = bool(ping)
    except Exception as e:
        out["details"]["inspect_error"] = str(e)
    return out


@router.get("/health")
async def ops_health():
    """Comprehensive health snapshot: broker_ok, db_ok, with details. (No SMTP)"""
    out = {"broker_ok": False, "db_ok": False, "details": {}}
    # DB
    try:
        ok = db_client.healthy() if hasattr(db_client, "healthy") else False
        out["db_ok"] = bool(ok)
        if not ok:
            out["details"]["db_error"] = getattr(db_client, "_error", "uninitialized")
    except Exception as e:
        out["details"]["db_error"] = str(e)
    # Broker
    try:
        insp = celery_app.control.inspect(timeout=2.0)
        ping = insp.ping() or {}
        out["details"]["inspect_ping"] = ping
        out["broker_ok"] = bool(ping)
    except Exception as e:
        out["details"]["inspect_error"] = str(e)
    return out


@router.post("/revoke")
async def revoke_task(task_id: str,
                      current_user: dict = Depends(get_current_active_user),
                      tasks_collection: Collection = Depends(get_tasks_collection)):
    """Revoke a scheduled reminder by task_id and mark it as cancelled.

    Enforces user scoping and idempotency.
    """
    doc = tasks_collection.find_one({"_id": task_id, "user_id": current_user["user_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    celery_id = doc.get("celery_task_id")
    if celery_id:
        try:
            celery_app.control.revoke(celery_id, terminate=False)
        except Exception:
            pass
    now = datetime.utcnow()
    tasks_collection.update_one({"_id": task_id}, {"$set": {"status": "cancelled", "updated_at": now}})
    return {"ok": True, "revoked": bool(celery_id), "task_id": task_id, "status": "cancelled"}


@router.get("/celery_inspect")
async def celery_inspect():
    """Return Celery inspector output (scheduled, active, reserved, registered)."""
    out = {}
    try:
        insp = celery_app.control.inspect(timeout=2.0)
        out["scheduled"] = insp.scheduled() or {}
        out["active"] = insp.active() or {}
        out["reserved"] = insp.reserved() or {}
        out["registered"] = insp.registered() or {}
        out["stats"] = insp.stats() or {}
    except Exception as e:
        out["error"] = str(e)
    return out


## Removed: /resync endpoint (reconcile task scheduling is no longer applicable)


## Removed: /send_test_email endpoint


## Removed: /schedule_test_reminder endpoint


@router.get("/peek_task")
async def peek_task(id: str,
                    current_user: dict = Depends(get_current_active_user),
                    tasks_collection: Collection = Depends(get_tasks_collection)):
    """Inspect a single task owned by the current user by id.

    Returns core fields useful for debugging reminder scheduling and delivery.
    """
    # Accept either string ids or hex that may be ObjectId in other collections; here tasks use string _id
    doc = tasks_collection.find_one({"_id": id, "user_id": str(current_user.get("user_id") or current_user.get("_id"))})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found for current user")
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title"),
        "due_date": doc.get("due_date"),
        "status": doc.get("status"),
        "celery_task_id": doc.get("celery_task_id"),
        "last_sent_at": doc.get("last_sent_at"),
        "sent_count": doc.get("sent_count", 0),
        "tags": doc.get("tags", []),
    }


@router.get("/list_recent_tasks")
async def list_recent_tasks(limit: int = 20,
                            current_user: dict = Depends(get_current_active_user),
                            tasks_collection: Collection = Depends(get_tasks_collection)):
    """List the most recently created tasks for the current user (any status)."""
    user_id = str(current_user.get("user_id") or current_user.get("_id"))
    cursor = tasks_collection.find({"user_id": user_id}).sort("created_at", -1).limit(max(1, min(100, limit)))
    out = []
    for doc in cursor:
        out.append({
            "id": str(doc.get("_id")),
            "title": doc.get("title"),
            "due_date": doc.get("due_date"),
            "status": doc.get("status"),
            "celery_task_id": doc.get("celery_task_id"),
            "last_sent_at": doc.get("last_sent_at"),
            "sent_count": doc.get("sent_count", 0),
            "tags": doc.get("tags", []),
        })
    return {"recent": out}
