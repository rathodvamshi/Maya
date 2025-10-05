# backend/app/routers/tasks.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.collection import Collection
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional

from app.database import get_tasks_collection, get_activity_logs_collection
from app.security import get_current_active_user
from app.models import (
    Task, TaskCreate, TaskUpdate, TaskBulkUpdate, 
    TaskStatus, TaskPriority, ActivityLog, ActivityType
)

router = APIRouter(
    prefix="/api/tasks",
    tags=["Tasks"],
    dependencies=[Depends(get_current_active_user)]
)

async def log_activity(user_id: str, activity_type: ActivityType, description: str, 
                      metadata: dict = None, activity_collection: Collection = None):
    """Helper function to log user activity."""
    if activity_collection:
        activity_log = ActivityLog(
            _id=str(ObjectId()),
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            metadata=metadata or {}
        )
        activity_collection.insert_one(activity_log.dict(by_alias=True))

# ======================================================
# TASK CRUD OPERATIONS
# ======================================================

@router.get("/", response_model=List[Task])
async def get_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    tag: Optional[str] = None,
    due_soon: Optional[bool] = None,
    overdue: Optional[bool] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get user's tasks with filtering options."""
    
    # Base query - only user's tasks
    query = {"user_id": current_user["user_id"]}
    
    # Apply filters
    if status:
        query["status"] = status.value
    
    if priority:
        query["priority"] = priority.value
    
    if tag:
        query["tags"] = {"$in": [tag]}
    
    # Date-based filters
    now = datetime.utcnow()
    if due_soon:
        # Tasks due in next 7 days
        next_week = now + timedelta(days=7)
        query["due_date"] = {
            "$gte": now,
            "$lte": next_week
        }
    
    if overdue:
        # Tasks past due date
        query["due_date"] = {"$lt": now}
        query["status"] = {"$ne": TaskStatus.DONE.value}
    
    # Execute query with pagination
    cursor = tasks_collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
    tasks = []
    
    for task_doc in cursor:
        task_doc["id"] = str(task_doc["_id"])
        del task_doc["_id"]
        tasks.append(Task(**task_doc))
    
    return tasks


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Create a new task."""
    
    # Create task document
    task_id = str(ObjectId())
    task_doc = {
        "_id": task_id,
        "user_id": current_user["user_id"],
        **task_data.dict(),
        "status": TaskStatus.TODO.value,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert task
    result = tasks_collection.insert_one(task_doc)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    
    # Log activity
    await log_activity(
        current_user["user_id"],
        ActivityType.TASK_CREATED,
        f"Created task: {task_data.title}",
        {"task_id": task_id},
        activity_collection
    )
    
    # Return created task
    task_doc["id"] = task_id
    del task_doc["_id"]
    return Task(**task_doc)


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get a specific task by ID."""
    
    try:
        task_doc = tasks_collection.find_one({
            "_id": task_id,
            "user_id": current_user["user_id"]
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_doc["id"] = str(task_doc["_id"])
    del task_doc["_id"]
    return Task(**task_doc)


@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Update a task."""
    
    # Check if task exists and belongs to user
    existing_task = tasks_collection.find_one({
        "_id": task_id,
        "user_id": current_user["user_id"]
    })
    
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prepare update data
    update_data = {}
    for field, value in task_data.dict(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value.value if hasattr(value, 'value') else value
    
    update_data["updated_at"] = datetime.utcnow()
    
    # Handle completion
    if update_data.get("status") == TaskStatus.DONE.value:
        update_data["completed_at"] = datetime.utcnow()
        
        # Log completion activity
        await log_activity(
            current_user["user_id"],
            ActivityType.TASK_COMPLETED,
            f"Completed task: {existing_task['title']}",
            {"task_id": task_id},
            activity_collection
        )
    
    # Update task
    result = tasks_collection.update_one(
        {"_id": task_id, "user_id": current_user["user_id"]},
        {"$set": update_data}
    )
    
    if not result.modified_count:
        raise HTTPException(status_code=500, detail="Failed to update task")
    
    # Return updated task
    updated_task = tasks_collection.find_one({"_id": task_id})
    updated_task["id"] = str(updated_task["_id"])
    del updated_task["_id"]
    return Task(**updated_task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Delete a task."""
    
    # Get task for activity logging
    existing_task = tasks_collection.find_one({
        "_id": task_id,
        "user_id": current_user["user_id"]
    })
    
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete task
    result = tasks_collection.delete_one({
        "_id": task_id,
        "user_id": current_user["user_id"]
    })
    
    if not result.deleted_count:
        raise HTTPException(status_code=500, detail="Failed to delete task")
    
    # Log activity
    await log_activity(
        current_user["user_id"],
        ActivityType.TASK_CREATED,  # We can add TASK_DELETED to enum later
        f"Deleted task: {existing_task['title']}",
        {"task_id": task_id},
        activity_collection
    )
    
    return {"message": "Task deleted successfully"}


# ======================================================
# BULK OPERATIONS
# ======================================================

@router.post("/bulk")
async def bulk_update_tasks(
    bulk_data: TaskBulkUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Perform bulk operations on tasks."""
    
    if not bulk_data.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")
    
    # Verify all tasks belong to current user
    query = {
        "_id": {"$in": bulk_data.task_ids},
        "user_id": current_user["user_id"]
    }
    
    existing_count = tasks_collection.count_documents(query)
    if existing_count != len(bulk_data.task_ids):
        raise HTTPException(status_code=404, detail="Some tasks not found or access denied")
    
    result_message = ""
    
    if bulk_data.operation == "delete":
        # Delete tasks
        result = tasks_collection.delete_many(query)
        result_message = f"Deleted {result.deleted_count} tasks"
        
        # Log activity
        await log_activity(
            current_user["user_id"],
            ActivityType.TASK_CREATED,  # Add bulk operations to enum later
            f"Bulk deleted {result.deleted_count} tasks",
            {"task_ids": bulk_data.task_ids},
            activity_collection
        )
    
    elif bulk_data.operation == "complete":
        # Mark tasks as completed
        update_data = {
            "status": TaskStatus.DONE.value,
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = tasks_collection.update_many(query, {"$set": update_data})
        result_message = f"Completed {result.modified_count} tasks"
        
        # Log activity
        await log_activity(
            current_user["user_id"],
            ActivityType.TASK_COMPLETED,
            f"Bulk completed {result.modified_count} tasks",
            {"task_ids": bulk_data.task_ids},
            activity_collection
        )
    
    elif bulk_data.operation == "update_status" and bulk_data.status:
        # Update status
        update_data = {
            "status": bulk_data.status.value,
            "updated_at": datetime.utcnow()
        }
        if bulk_data.status == TaskStatus.DONE:
            update_data["completed_at"] = datetime.utcnow()
        
        result = tasks_collection.update_many(query, {"$set": update_data})
        result_message = f"Updated status for {result.modified_count} tasks"
    
    elif bulk_data.operation == "update_priority" and bulk_data.priority:
        # Update priority
        update_data = {
            "priority": bulk_data.priority.value,
            "updated_at": datetime.utcnow()
        }
        result = tasks_collection.update_many(query, {"$set": update_data})
        result_message = f"Updated priority for {result.modified_count} tasks"
    
    else:
        raise HTTPException(status_code=400, detail="Invalid bulk operation")
    
    return {"message": result_message}


# ======================================================
# TASK STATISTICS
# ======================================================

@router.get("/stats/summary")
async def get_task_stats(
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get task statistics summary."""
    
    try:
        user_id = current_user["user_id"]
        
        # Aggregate statistics
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "todo": {"$sum": {"$cond": [{"$eq": ["$status", "todo"]}, 1, 0]}},
                    "in_progress": {"$sum": {"$cond": [{"$eq": ["$status", "in_progress"]}, 1, 0]}},
                    "done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}},
                    "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
                    "overdue": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$lt": ["$due_date", datetime.utcnow()]},
                                        {"$ne": ["$status", "done"]}
                                    ]
                                },
                                1, 0
                            ]
                        }
                    }
                }
            }
        ]
        
        result = list(tasks_collection.aggregate(pipeline))
        
        if not result:
            return {
                "total": 0,
                "todo": 0,
                "in_progress": 0,
                "done": 0,
                "cancelled": 0,
                "overdue": 0
            }
        
        stats = result[0]
        del stats["_id"]
        return stats
        
    except Exception as e:
        # Return fallback stats
        return {
            "total": 0,
            "todo": 0,
            "in_progress": 0,
            "done": 0,
            "cancelled": 0,
            "overdue": 0
        }


@router.get("/stats/priority")
async def get_priority_stats(
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get task statistics by priority."""
    
    user_id = current_user["user_id"]
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": "$priority",
                "count": {"$sum": 1},
                "completed": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}}
            }
        }
    ]
    
    result = list(tasks_collection.aggregate(pipeline))
    return {item["_id"]: {"count": item["count"], "completed": item["completed"]} for item in result}


@router.get("/tags")
async def get_user_tags(
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection)
):
    """Get all tags used by the user."""
    
    user_id = current_user["user_id"]
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    result = list(tasks_collection.aggregate(pipeline))
    return [{"tag": item["_id"], "count": item["count"]} for item in result]