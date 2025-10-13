# backend/app/routes/tasks.py
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId, errors
import dateparser
import pytz
import logging
from pymongo.errors import OperationFailure

from app.models import (
    Task,
    TaskCreate,
    TaskUpdate,
    TaskBulkUpdate,
    TaskStatus,
    TaskPriority,
)
from app.database import get_tasks_collection
from app.security import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tasks",
    tags=["Tasks"],
    dependencies=[Depends(get_current_active_user)],
)

# --------- Configuration / constants ----------
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200
DUE_SOON_DAYS_DEFAULT = 7

# --------- Utility helpers --------------------

def _str_oid(oid: Any) -> str:
    """Convert ObjectId or string id to string representation."""
    if isinstance(oid, str):
        return oid
    try:
        return str(oid)
    except Exception:
        return str(oid)

def _user_id_value(current_user: dict) -> Any:
    """Return user id in the form stored in DB (prefer existing shapes)."""
    return current_user.get("user_id") or current_user.get("userId") or current_user.get("_id")

def _make_user_match(user_id: Any) -> Dict[str, Any]:
    """
    Return a Mongo-friendly match that tolerates stored userId as either string or ObjectId.
    Use this in queries like {"$or": [{ "user_id": user_id }, { "user_id": ObjectId(user_id) }]}
    """
    clauses = []
    if user_id is not None:
        clauses.append({"user_id": user_id})
        try:
            if isinstance(user_id, str) and ObjectId.is_valid(user_id):
                clauses.append({"user_id": ObjectId(user_id)})
        except Exception:
            # non-fatal
            pass
    return {"$or": clauses} if clauses else {}

def _ensure_objectid_or_pass(val: str) -> Any:
    """Try to convert to ObjectId, otherwise return original string (tolerate string _id storage)."""
    try:
        return ObjectId(val)
    except Exception:
        return val

def _to_naive_utc_from_dt(dt_obj: datetime) -> datetime:
    """Convert any aware datetime to naive UTC for storage; or accept naive as already UTC."""
    if dt_obj is None:
        return None
    try:
        if dt_obj.tzinfo is None:
            return dt_obj
        return dt_obj.astimezone(pytz.UTC).replace(tzinfo=None)
    except Exception:
        # Defensive fallback
        return dt_obj

def _to_naive_utc_from_parsed(dt_obj: Optional[datetime]) -> Optional[datetime]:
    return _to_naive_utc_from_dt(dt_obj) if dt_obj is not None else None

# --------- Date parsing --------------------------------
def _parse_when_to_due_date(when: Optional[str], timezone: Optional[str], prefer_future: bool = True) -> Optional[datetime]:
    """
    Parse a 'when' expression (natural language) into a naive UTC datetime for storage.
    Returns naive UTC datetime (tzinfo removed) or None on failure.
    """
    if not when:
        return None
    try:
        tzname = timezone or "UTC"
        settings = {
            "TIMEZONE": tzname,
            "TO_TIMEZONE": "UTC",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future" if prefer_future else "past",
        }
        dt = dateparser.parse(when, settings=settings)
        if dt:
            # convert to UTC and remove tzinfo for Mongo naive storage convention
            dt_utc = dt.astimezone(pytz.UTC).replace(tzinfo=None)
            return dt_utc
    except Exception as exc:
        logger.debug("dateparser parse error for %r tz=%r: %s", when, timezone, exc)
    return None

# --------- Index helper (call on startup) ----------
def create_task_indexes(tasks_collection):
    """
    Helper to create recommended indexes.
    Call this from app startup (once).
    Indexes:
      - user_id + due_date (for due/overdue/due_soon queries)
      - user_id + status (for quick status queries)
      - text index on title + description for search
    """
    try:
        # Align names with global index definitions in app.database.ensure_indexes
        try:
            tasks_collection.create_index([("user_id", 1), ("due_date", 1)], name="user_due_date", background=True)
        except OperationFailure as of:
            # Ignore options conflict if an equivalent index already exists under another name
            if getattr(of, "code", None) != 85:
                raise
        try:
            tasks_collection.create_index([("user_id", 1), ("status", 1)], name="user_status", background=True)
        except OperationFailure as of:
            if getattr(of, "code", None) != 85:
                raise
        # create text index with weights to prioritize title
        try:
            tasks_collection.create_index([("title", "text"), ("description", "text")], name="task_text_idx", default_language="english", background=True)
        except OperationFailure as of:
            if getattr(of, "code", None) != 85:
                raise
        logger.info("Task indexes ensured.")
    except Exception as exc:
        logger.exception("Failed to create task indexes: %s", exc)

# --------- Response normalization --------------------
def _to_task_response(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize DB document to a JSON-serializable dict that matches Task model shape.
    Keeps backward compatibility: converts _id to string and ensures default fields exist.
    """
    out = dict(doc)
    if "_id" in out:
        out["_id"] = _str_oid(out["_id"])
    out.setdefault("status", TaskStatus.TODO)
    out.setdefault("priority", TaskPriority.MEDIUM)
    out.setdefault("tags", out.get("tags") or [])
    return out

# ===========================
# CRUD & endpoints
# ===========================

@router.get("/")
async def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    due_soon: Optional[bool] = Query(False),
    overdue: Optional[bool] = Query(False),
    search: Optional[str] = Query(None, description="Full-text search on title & description"),
    sort_by: Optional[str] = Query("updated_at", description="Sort field: updated_at | due_date | created_at"),
    sort_dir: Optional[int] = Query(-1, ge=-1, le=1, description="Sort direction: 1 asc, -1 desc"),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    """
    List tasks for the user with flexible filtering, search, sorting and pagination.
    Implements defensive handling of user_id shapes and optimized queries for due_soon/overdue.
    """
    user_id = _user_id_value(current_user)
    if not user_id:
        return []

    # Ensure indexes exist if necessary (non-blocking; safe to call multiple times)
    try:
        create_task_indexes(tasks)
    except Exception:
        logger.debug("Index creation attempted (may have been created before).")

    query: Dict[str, Any] = {"user_id": user_id}

    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if tag:
        # match membership in array or exact
        query["tags"] = tag

    now = datetime.utcnow()
    # overdue overrides due_soon
    if overdue:
        query["due_date"] = {"$lt": now}
        # exclude completed/cancelled when counting overdue unless explicit
        query.setdefault("status", {"$nin": ["done", "cancelled"]})
    elif due_soon:
        window_end = now + timedelta(days=DUE_SOON_DAYS_DEFAULT)
        query["due_date"] = {"$gte": now, "$lte": window_end}

    # Search: prefer text index when available
    cursor = None
    try:
        if search:
            # Use Mongo's $text search if index present; fallback to regex on title/description
            try:
                cursor = tasks.find({**query, "$text": {"$search": search}}, {"score": {"$meta": "textScore"}})
                # sort by score desc then requested sort
                cursor = cursor.sort([("score", {"$meta": "textScore"})])
            except Exception:
                # fallback regex
                regex = {"$regex": search, "$options": "i"}
                cursor = tasks.find({**query, "$or": [{"title": regex}, {"description": regex}]})
        else:
            cursor = tasks.find(query)
    except Exception as exc:
        logger.exception("Task listing query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to query tasks")

    # Sorting and pagination
    if cursor is not None:
        sort_field = sort_by if sort_by in {"updated_at", "due_date", "created_at"} else "updated_at"
        sort_direction = int(sort_dir) if sort_dir in (-1, 1) else -1
        cursor = cursor.sort(sort_field, sort_direction).skip(offset).limit(limit)

    items: List[Dict[str, Any]] = []
    try:
        for d in cursor:
            # normalize id and fields
            items.append(_to_task_response(d))
    except Exception as exc:
        logger.exception("Error iterating tasks cursor: %s", exc)
        raise HTTPException(status_code=500, detail="Error reading tasks")

    return items

# alias to avoid strict slash issues
@router.get("")
async def list_tasks_alias(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    due_soon: Optional[bool] = Query(False),
    overdue: Optional[bool] = Query(False),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("updated_at"),
    sort_dir: Optional[int] = Query(-1),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    return await list_tasks(status, priority, tag, due_soon, overdue, search, sort_by, sort_dir, limit, offset, current_user, tasks)  # type: ignore[arg-type]


@router.post("/", response_model=Task)
async def create_task(
    task_in: TaskCreate,
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    """
    Create a new task. Accepts either due_date explicitly (ISO string / datetime) or a natural language 'when' with timezone.
    Stores due_date as naive UTC datetime in Mongo.
    Disallows creating tasks in the past by default to avoid accidental scheduling; set allow_past True in request if needed.
    """
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")

    # Resolve due date: priority order: explicit due_date field -> when + timezone
    due_date = None
    if getattr(task_in, "due_date", None):
        # if pydantic parsed it to a datetime, use as provided; if string, try parse
        if isinstance(task_in.due_date, datetime):
            due_date = task_in.due_date
        else:
            try:
                # Try iso format parse using dateparser fallback
                parsed = _parse_when_to_due_date(str(task_in.due_date), task_in.timezone or None, prefer_future=True)
                due_date = parsed
            except Exception:
                due_date = None
    elif getattr(task_in, "when", None):
        due_date = _parse_when_to_due_date(task_in.when, task_in.timezone or None, prefer_future=True)

    # If due_date present, ensure not in past unless allow_past True
    if due_date and not getattr(task_in, "allow_past", False):
        now = datetime.utcnow()
        if due_date <= now:
            raise HTTPException(status_code=400, detail="due_date must be in the future")

    # build document with safe defaults
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "title": task_in.title.strip(),
        "description": (task_in.description or "").strip(),
        "status": task_in.status or TaskStatus.TODO,
        "priority": task_in.priority or TaskPriority.MEDIUM,
        "due_date": _to_naive_utc_from_parsed(due_date),
        "tags": task_in.tags or [],
        "recurrence": task_in.recurrence,
        "created_at": now,
        "updated_at": now,
    }

    try:
        res = tasks.insert_one(doc)
    except Exception as exc:
        logger.exception("Failed to insert task: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create task")

    created = tasks.find_one({"_id": res.inserted_id})
    if not created:
        raise HTTPException(status_code=500, detail="Task created but could not be read back")

    # convert _id for pydantic model
    created["_id"] = str(created["_id"])
    return Task(**created)


@router.post("")
async def create_task_alias(
    task_in: TaskCreate,
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    return await create_task(task_in, current_user, tasks)  # type: ignore[arg-type]


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")

    # try ObjectId then fallback to string id toleration
    query = {"user_id": user_id}
    try:
        oid = ObjectId(task_id)
        query["_id"] = oid
    except Exception:
        query["_id"] = task_id

    doc = tasks.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    doc["_id"] = str(doc["_id"])
    return Task(**doc)


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    updates: TaskUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    """
    Partial update of a task. If due_date provided as string (natural language), attempt to parse
    using the optional timezone included in the request body (updates.timezone).
    """
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")

    data = updates.model_dump(exclude_unset=True)
    if "due_date" in data and isinstance(data["due_date"], str):
        parsed = _parse_when_to_due_date(data["due_date"], data.get("timezone"))
        if parsed:
            data["due_date"] = parsed
        else:
            # try to allow ISO string
            try:
                iso_dt = dateparser.parse(data["due_date"], settings={"RETURN_AS_TIMEZONE_AWARE": True})
                if iso_dt:
                    data["due_date"] = iso_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                else:
                    data.pop("due_date", None)
            except Exception:
                data.pop("due_date", None)

    # if due_date present, ensure not in the past unless explicitly allowed
    if "due_date" in data and data["due_date"] is not None and not data.get("allow_past", False):
        if isinstance(data["due_date"], datetime) and data["due_date"] <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="due_date must be in the future")

    data["updated_at"] = datetime.utcnow()
    try:
        oid = ObjectId(task_id)
        res = tasks.update_one({"_id": oid, "user_id": user_id}, {"$set": data})
    except Exception:
        # fallback to string _id
        res = tasks.update_one({"_id": task_id, "user_id": user_id}, {"$set": data})

    if getattr(res, "matched_count", 0) == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True}


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    user_id = _user_id_value(current_user)
    try:
        oid = ObjectId(task_id)
        res = tasks.delete_one({"_id": oid, "user_id": user_id})
    except Exception:
        res = tasks.delete_one({"_id": task_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True}


@router.post("/bulk")
async def bulk_update(
    payload: TaskBulkUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")

    ids: List[Any] = []
    for tid in payload.task_ids:
        try:
            ids.append(ObjectId(tid))
        except Exception:
            ids.append(tid)

    q = {"_id": {"$in": ids}, "user_id": user_id}

    # Perform operation and return per-id info where helpful
    if payload.operation == "delete":
        res = tasks.delete_many(q)
        return {"success": True, "deleted": res.deleted_count}
    elif payload.operation == "complete":
        now = datetime.utcnow()
        res = tasks.update_many(q, {"$set": {"status": TaskStatus.DONE, "completed_at": now, "updated_at": now}})
        return {"success": True, "updated": res.modified_count}
    elif payload.operation == "update_status" and payload.status:
        res = tasks.update_many(q, {"$set": {"status": payload.status, "updated_at": datetime.utcnow()}})
        return {"success": True, "updated": res.modified_count}
    elif payload.operation == "update_priority" and payload.priority:
        res = tasks.update_many(q, {"$set": {"priority": payload.priority, "updated_at": datetime.utcnow()}})
        return {"success": True, "updated": res.modified_count}
    else:
        raise HTTPException(status_code=400, detail="Invalid bulk operation")

# ----------------------------
# STATS & TAGS (improved)
# ----------------------------
@router.get("/stats/summary")
async def task_stats_summary(
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")

    try:
        total = tasks.count_documents({"user_id": user_id})
        now = datetime.utcnow()
        overdue = tasks.count_documents({"user_id": user_id, "due_date": {"$lt": now}, "status": {"$nin": ["done", "cancelled"]}})
        def _count(q):
            return tasks.count_documents({"user_id": user_id, **q})
        return {
            "total": total,
            "todo": _count({"status": "todo"}),
            "in_progress": _count({"status": "in_progress"}),
            "done": _count({"status": "done"}),
            "cancelled": _count({"status": "cancelled"}),
            "overdue": overdue,
        }
    except Exception as exc:
        logger.exception("Failed to compute stats: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to compute stats")

@router.get("/stats/priority")
async def task_priority_stats(
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
    ]
    agg = list(tasks.aggregate(pipeline))
    base = {"low": 0, "medium": 0, "high": 0, "urgent": 0}
    for row in agg:
        key = (row.get("_id") or "").lower()
        if key in base:
            base[key] = row.get("count", 0)
    return base

@router.get("/tags")
async def user_tags(
    current_user: dict = Depends(get_current_active_user),
    tasks = Depends(get_tasks_collection),
):
    user_id = _user_id_value(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")
    try:
        tags = tasks.distinct("tags", {"user_id": user_id})
        uniq = set()
        for t in tags:
            if isinstance(t, list):
                for s in t:
                    if isinstance(s, str):
                        uniq.add(s)
            elif isinstance(t, str):
                uniq.add(t)
        return sorted(uniq)
    except Exception as exc:
        logger.exception("Failed to fetch tags: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch tags")
