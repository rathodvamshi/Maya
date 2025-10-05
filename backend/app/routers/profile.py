# backend/app/routers/profile.py

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pymongo.collection import Collection
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional
import hashlib
import secrets
import base64

from app.database import (
    get_user_profile_collection, get_api_keys_collection, 
    get_activity_logs_collection, get_security_events_collection,
    get_tasks_collection, get_sessions_collection
)
from app.security import get_current_active_user
from app.models import (
    UserProfile, UserUpdateProfile, UserStats, DashboardStats,
    APIKey, APIKeyCreate, APIKeyPublic,
    ActivityLog, SecurityEvent, ActivityType
)

router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"],
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
# PROFILE MANAGEMENT
# ======================================================

@router.get("/", response_model=UserProfile)
async def get_profile(
    current_user: dict = Depends(get_current_active_user),
    profile_collection: Collection = Depends(get_user_profile_collection)
):
    """Get user profile with robust fallbacks.

    Normalizes user id access (user_id / userId / _id) to reduce KeyError risks
    and eliminates unreachable code paths present in earlier implementation.
    """
    user_id = current_user.get("user_id") or current_user.get("userId") or current_user.get("_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user context")

    try:
        profile_doc = profile_collection.find_one({"user_id": user_id})
        if not profile_doc:
            profile_doc = {
                "_id": str(ObjectId()),
                "user_id": user_id,
                "name": current_user.get("name", "User"),
                "bio": None,
                "avatar_url": None,
                "timezone": "UTC",
                "language": "en",
                "theme": "dark",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            profile_collection.insert_one(profile_doc)
        # Ensure string id
        profile_doc["_id"] = str(profile_doc["_id"])
        return UserProfile(**profile_doc)
    except Exception:
        # Minimal fallback profile (no DB dependency)
        return UserProfile(
            _id=str(ObjectId()),
            user_id=user_id,
            name=current_user.get("name", "User"),
            bio=None,
            avatar_url=None,
            timezone="UTC",
            language="en",
            theme="dark",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )


@router.put("/", response_model=UserProfile)
async def update_profile(
    profile_data: UserUpdateProfile,
    current_user: dict = Depends(get_current_active_user),
    profile_collection: Collection = Depends(get_user_profile_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Update user profile."""
    
    # Prepare update data
    update_data = {}
    for field, value in profile_data.dict(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    update_data["updated_at"] = datetime.utcnow()
    
    # Update profile
    result = profile_collection.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": update_data},
        upsert=True
    )
    
    # Log activity
    await log_activity(
        current_user["user_id"],
        ActivityType.PROFILE_UPDATED,
        "Updated profile information",
        {"updated_fields": list(update_data.keys())},
        activity_collection
    )
    
    # Return updated profile
    updated_profile = profile_collection.find_one({"user_id": current_user["user_id"]})
    updated_profile["id"] = str(updated_profile["_id"])
    del updated_profile["_id"]
    return UserProfile(**updated_profile)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    profile_collection: Collection = Depends(get_user_profile_collection)
):
    """Upload user avatar."""
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Validate file size (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    # For now, we'll store as base64 data URL
    # In production, you'd upload to cloud storage
    file_extension = file.filename.split('.')[-1].lower()
    if file_extension not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    # Create data URL
    base64_content = base64.b64encode(content).decode('utf-8')
    data_url = f"data:{file.content_type};base64,{base64_content}"
    
    # Update profile
    result = profile_collection.update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"avatar_url": data_url, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    
    return {"message": "Avatar uploaded successfully", "avatar_url": data_url}


# ======================================================
# USER STATISTICS
# ======================================================

@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    current_user: dict = Depends(get_current_active_user),
    tasks_collection: Collection = Depends(get_tasks_collection),
    sessions_collection: Collection = Depends(get_sessions_collection)
):
    """Get user statistics."""
    
    user_id = current_user["user_id"]
    
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
    
    # Get session stats
    session_stats = sessions_collection.aggregate([
        {"$match": {"userId": user_id}},  # Note: sessions use userId not user_id
        {
            "$group": {
                "_id": None,
                "total_chats": {"$sum": 1},
                "total_messages": {"$sum": {"$size": "$messages"}},
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
    
    # Calculate average session length (messages per session)
    avg_session_length = total_messages / total_chats if total_chats > 0 else 0
    
    return UserStats(
        total_chats=total_chats,
        total_messages=total_messages,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        active_sessions=active_sessions,
        avg_session_length=round(avg_session_length, 1)
    )


# ======================================================
# API KEY MANAGEMENT
# ======================================================

@router.get("/api-keys", response_model=List[APIKeyPublic])
async def get_api_keys(
    current_user: dict = Depends(get_current_active_user),
    api_keys_collection: Collection = Depends(get_api_keys_collection)
):
    """Get user's API keys."""
    
    keys = api_keys_collection.find({
        "user_id": current_user["user_id"],
        "is_active": True
    }).sort("created_at", -1)
    
    result = []
    for key_doc in keys:
        key_doc["id"] = str(key_doc["_id"])
        del key_doc["_id"]
        # Remove sensitive data
        del key_doc["hashed_key"]
        result.append(APIKeyPublic(**key_doc))
    
    return result


@router.post("/api-keys", response_model=dict)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: dict = Depends(get_current_active_user),
    api_keys_collection: Collection = Depends(get_api_keys_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Create a new API key."""
    
    # Check API key limit (max 10 per user)
    existing_count = api_keys_collection.count_documents({
        "user_id": current_user["user_id"],
        "is_active": True
    })
    
    if existing_count >= 10:
        raise HTTPException(
            status_code=400, 
            detail="Maximum number of API keys reached (10)"
        )
    
    # Generate API key
    raw_key = secrets.token_urlsafe(32)
    api_key = f"maya_{raw_key}"
    
    # Hash the key for storage
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Create key preview (first 8 chars + "...")
    key_preview = f"{api_key[:12]}..."
    
    # Create API key document
    key_id = str(ObjectId())
    key_doc = {
        "_id": key_id,
        "user_id": current_user["user_id"],
        "name": key_data.name,
        "description": key_data.description,
        "key_preview": key_preview,
        "hashed_key": hashed_key,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    # Insert API key
    result = api_keys_collection.insert_one(key_doc)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create API key")
    
    # Log activity
    await log_activity(
        current_user["user_id"],
        ActivityType.API_KEY_CREATED,
        f"Created API key: {key_data.name}",
        {"api_key_id": key_id, "key_name": key_data.name},
        activity_collection
    )
    
    return {
        "message": "API key created successfully",
        "api_key": api_key,  # Return full key only once
        "key_preview": key_preview,
        "warning": "Store this key safely. You won't be able to see it again."
    }


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_active_user),
    api_keys_collection: Collection = Depends(get_api_keys_collection),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Delete an API key."""
    
    # Get key for activity logging
    existing_key = api_keys_collection.find_one({
        "_id": key_id,
        "user_id": current_user["user_id"]
    })
    
    if not existing_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Soft delete (mark as inactive)
    result = api_keys_collection.update_one(
        {"_id": key_id, "user_id": current_user["user_id"]},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if not result.modified_count:
        raise HTTPException(status_code=500, detail="Failed to delete API key")
    
    # Log activity
    await log_activity(
        current_user["user_id"],
        ActivityType.API_KEY_DELETED,
        f"Deleted API key: {existing_key['name']}",
        {"api_key_id": key_id, "key_name": existing_key['name']},
        activity_collection
    )
    
    return {"message": "API key deleted successfully"}


# ======================================================
# ACTIVITY & SECURITY LOGS
# ======================================================

@router.get("/activity", response_model=List[ActivityLog])
async def get_activity_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_active_user),
    activity_collection: Collection = Depends(get_activity_logs_collection)
):
    """Get user activity logs."""
    
    logs = activity_collection.find({
        "user_id": current_user["user_id"]
    }).sort("timestamp", -1).skip(offset).limit(limit)
    
    result = []
    for log_doc in logs:
        log_doc["id"] = str(log_doc["_id"])
        del log_doc["_id"]
        result.append(ActivityLog(**log_doc))
    
    return result


@router.get("/security", response_model=List[SecurityEvent])
async def get_security_events(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_active_user),
    security_collection: Collection = Depends(get_security_events_collection)
):
    """Get user security events."""
    
    events = security_collection.find({
        "user_id": current_user["user_id"]
    }).sort("timestamp", -1).skip(offset).limit(limit)
    
    result = []
    for event_doc in events:
        event_doc["id"] = str(event_doc["_id"])
        del event_doc["_id"]
        result.append(SecurityEvent(**event_doc))
    
    return result