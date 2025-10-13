# backend/app/routers/dashboard.py

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.collection import Collection
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.database import (
    get_user_profile_collection, get_tasks_collection, 
    get_sessions_collection, get_activity_logs_collection
)
from app.security import get_current_active_user
from app.models import DashboardStats, UserStats, ActivityLog, SessionPublic

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_active_user)]
)

# ======================================================
# DASHBOARD DATA
# ======================================================

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    sessions_collection: Collection = Depends(get_sessions_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Get comprehensive dashboard statistics."""

    user_id = current_user.get("user_id") or current_user.get("userId") or current_user.get("_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")
    
    # Get user statistics
    try:
        user_stats = await get_user_statistics(user_id, tasks_collection, sessions_collection)
    except Exception:
        # Defensive default to avoid 500s on aggregation errors
        user_stats = UserStats()
    
    # Get recent activity (last 10 items)
    try:
        recent_activity = await get_recent_activity(user_id, activity_collection, limit=10)
    except Exception:
        recent_activity = []
    
    # Get recent chats (last 5 sessions)
    try:
        recent_chats = await get_recent_chats(user_id, sessions_collection, limit=5)
    except Exception:
        recent_chats = []
    
    # Get task summary
    try:
        task_summary = await get_task_summary(user_id, tasks_collection)
    except Exception:
        task_summary = {"todo": 0, "in_progress": 0, "done": 0, "cancelled": 0, "overdue": 0}
    
    return DashboardStats(
        user_stats=user_stats,
        recent_activity=recent_activity,
        recent_chats=recent_chats,
        task_summary=task_summary
    )


async def get_user_statistics(user_id: str, tasks_collection: Collection, sessions_collection: Collection) -> UserStats:
    """Get user statistics."""
    
    # Get task stats
    task_stats = tasks_collection.aggregate([
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": None,
                "total_tasks": {"$sum": 1},
                "completed_tasks": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}}
            }
        }
    ])
    
    task_result = list(task_stats)
    total_tasks = task_result[0]["total_tasks"] if task_result else 0
    completed_tasks = task_result[0]["completed_tasks"] if task_result else 0
    
    # Get session stats — support both string and ObjectId types for userId
    match = {"$or": [{"userId": user_id}]}
    from bson import ObjectId
    if isinstance(user_id, str) and ObjectId.is_valid(user_id):
        match["$or"].append({"userId": ObjectId(user_id)})

    session_stats = sessions_collection.aggregate([
        {"$match": match},  # Note: sessions use userId not user_id
        {
            "$group": {
                "_id": None,
                "total_chats": {"$sum": 1},
                # Guard against missing messages field
                "total_messages": {"$sum": {"$cond": [{"$isArray": "$messages"}, {"$size": "$messages"}, 0]}},
                "active_sessions": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$isArchived", False]},
                            1, 0
                        ]
                    }
                }
            }
        }
    ])
    
    session_result = list(session_stats)
    total_chats = session_result[0]["total_chats"] if session_result else 0
    total_messages = session_result[0]["total_messages"] if session_result else 0
    active_sessions = session_result[0]["active_sessions"] if session_result else 0
    
    # Calculate average session length
    avg_session_length = total_messages / total_chats if total_chats > 0 else 0
    
    return UserStats(
        total_chats=total_chats,
        total_messages=total_messages,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        active_sessions=active_sessions,
        avg_session_length=round(avg_session_length, 1)
    )


async def get_recent_activity(user_id: str, activity_collection: Collection, limit: int = 10) -> List[ActivityLog]:
    """Get recent user activity."""
    
    logs = activity_collection.find({
        "user_id": user_id
    }).sort("timestamp", -1).limit(limit)
    
    result = []
    for log_doc in logs:
        log_doc["id"] = str(log_doc["_id"])
        del log_doc["_id"]
        result.append(ActivityLog(**log_doc))
    
    return result


async def get_recent_chats(user_id: str, sessions_collection: Collection, limit: int = 5) -> List[SessionPublic]:
    """Get recent chat sessions."""
    
    from bson import ObjectId
    user_match = {"$or": [{"userId": user_id}]}
    if isinstance(user_id, str) and ObjectId.is_valid(user_id):
        user_match["$or"].append({"userId": ObjectId(user_id)})

    sessions = sessions_collection.find({
        **user_match,
        "$or": [
            {"isArchived": {"$ne": True}},
            {"isArchived": {"$exists": False}}
        ]
    }).sort("updatedAt", -1).limit(limit)
    
    result = []
    for session_doc in sessions:
        # Get preview from last user message
        preview = None
        if session_doc.get("messages"):
            for msg in reversed(session_doc["messages"]):
                if msg.get("sender") == "user":
                    preview = msg["text"][:100] + "..." if len(msg["text"]) > 100 else msg["text"]
                    break
        
        session_public = SessionPublic(
            id=str(session_doc.get("_id")),
            title=session_doc.get("title", "Untitled Chat"),
            created_at=session_doc.get("createdAt", datetime.utcnow()),
            last_updated_at=session_doc.get("lastUpdatedAt", session_doc.get("updatedAt", datetime.utcnow())),
            message_count=len(session_doc.get("messages", [])),
            preview=preview
        )
        result.append(session_public)
    
    return result


async def get_task_summary(user_id: str, tasks_collection: Collection) -> Dict[str, int]:
    """Get task summary by status."""
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }
        }
    ]
    
    result = list(tasks_collection.aggregate(pipeline))
    
    # Initialize with default values
    summary = {
        "todo": 0,
        "in_progress": 0,
        "done": 0,
        "cancelled": 0,
        "overdue": 0
    }
    
    # Fill in actual counts
    for item in result:
        if item["_id"] in summary:
            summary[item["_id"]] = item["count"]
    
    # Calculate overdue tasks
    overdue_count = tasks_collection.count_documents({
        "user_id": user_id,
        "due_date": {"$lt": datetime.utcnow()},
        "status": {"$nin": ["done", "cancelled"]}
    })
    summary["overdue"] = overdue_count
    
    return summary


# ======================================================
# QUICK ACTIONS
# ======================================================

@router.get("/quick-stats")
async def get_quick_stats(
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    sessions_collection: Collection = Depends(get_sessions_collection)
):
    """Get quick statistics for dashboard widgets."""
    
    try:
        user_id = current_user.get("user_id") or current_user.get("userId") or current_user.get("_id")
        if not user_id:
            return {
                "tasks_today": 0,
                "completed_today": 0,
                "active_sessions": 0,
                "pending_tasks": 0,
                "productivity_score": 0
            }
        
        # Today's stats
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Tasks created today
        tasks_today = tasks_collection.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": today_start, "$lt": today_end}
        })
        
        # Tasks completed today
        completed_today = tasks_collection.count_documents({
            "user_id": user_id,
            "completed_at": {"$gte": today_start, "$lt": today_end}
        })
        
        # Active chat sessions — support both string and ObjectId userId types
        from bson import ObjectId
        uid_or = [{"userId": user_id}]
        if isinstance(user_id, str) and ObjectId.is_valid(user_id):
            uid_or.append({"userId": ObjectId(user_id)})
        active_sessions = sessions_collection.count_documents({
            "$and": [
                {"$or": uid_or},
                {"updatedAt": {"$gte": datetime.utcnow() - timedelta(hours=24)}}
            ]
        })
        
        # Total pending tasks
        pending_tasks = tasks_collection.count_documents({
            "user_id": user_id,
            "status": {"$in": ["todo", "in_progress"]}
        })
        
        return {
            "tasks_today": tasks_today,
            "completed_today": completed_today,
            "active_sessions": active_sessions,
            "pending_tasks": pending_tasks,
            "productivity_score": min(100, (completed_today * 20) + (tasks_today * 10))
        }
        
    except Exception:
        # Return fallback data
        return {
            "tasks_today": 0,
            "completed_today": 0,
            "active_sessions": 0,
            "pending_tasks": 0,
            "productivity_score": 0
        }


@router.get("/productivity-trends")
async def get_productivity_trends(
    days: int = 30,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get productivity trends over time."""

    user_id = current_user.get("user_id") or current_user.get("userId") or current_user.get("_id")
    if not user_id:
        return {"period_days": days, "completed_by_day": {}, "created_by_day": {}}
    
    # Calculate date range
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    start_date = end_date - timedelta(days=days)
    
    # Aggregate daily task completion
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "completed_at": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$completed_at"
                    }
                },
                "completed": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    completed_by_day = list(tasks_collection.aggregate(pipeline))
    
    # Aggregate daily task creation
    pipeline[0]["$match"]["completed_at"] = {"$gte": start_date, "$lte": end_date}
    pipeline[0]["$match"].pop("completed_at")
    pipeline[0]["$match"]["created_at"] = {"$gte": start_date, "$lte": end_date}
    pipeline[1]["$group"]["_id"]["$dateToString"]["date"] = "$created_at"
    pipeline[1]["$group"]["created"] = pipeline[1]["$group"].pop("completed")
    
    created_by_day = list(tasks_collection.aggregate(pipeline))
    
    return {
        "period_days": days,
        "completed_by_day": {item["_id"]: item["completed"] for item in completed_by_day},
        "created_by_day": {item["_id"]: item["created"] for item in created_by_day}
    }


@router.get("/upcoming-tasks")
async def get_upcoming_tasks(
    limit: int = 10,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get upcoming tasks (due soon)."""
    
    try:
        user_id = current_user.get("user_id") or current_user.get("userId") or current_user.get("_id")
        if not user_id:
            return []
        
        # Get tasks due in next 30 days
        now = datetime.utcnow()
        future_cutoff = now + timedelta(days=30)
        
        tasks = tasks_collection.find({
            "user_id": user_id,
            "due_date": {"$gte": now, "$lte": future_cutoff},
            "status": {"$nin": ["done", "cancelled"]}
        }).sort("due_date", 1).limit(limit)
        
        result = []
        for task_doc in tasks:
            task_doc["id"] = str(task_doc["_id"])
            del task_doc["_id"]
            result.append(task_doc)
        
        return result
        
    except Exception:
        # Return empty list as fallback
        return []