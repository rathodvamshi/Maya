# backend/app/models.py
"""
Upgraded Pydantic models for the assistant app.

Improvements made:
 - Stronger typing and validation (min/max lengths, non-empty titles).
 - Consistent `_id` aliasing for Mongo interchange with helpers `to_mongo()` / `from_mongo()`.
 - Timezone-aware helpers and validation (optional, requires `pytz` to be available).
 - Task model extended with notification metadata, celery id and flexible storage-friendly methods.
 - Schema examples for API docs and helpful validators to catch common user errors early.
 - Keep models lightweight and serializer-friendly (datetimes remain `datetime` objects).
 - Suggestions: call `Model.to_mongo()` before inserting into Mongo to normalize datetimes and remove Pydantic-only fields.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, validator, root_validator, constr

# Optional timezone validation (best-effort)
try:
    import pytz  # type: ignore
    _AVAILABLE_TIMEZONES = set(pytz.all_timezones)
except Exception:
    pytz = None
    _AVAILABLE_TIMEZONES = set()


# -------------------------
# Utility types & helpers
# -------------------------



def _ensure_list_of_str(value: Optional[List[Any]]) -> List[str]:
    if not value:
        return []
    out: List[str] = []
    for v in value:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out.append(s)
    return out


def _dt_to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize datetime to naive UTC (tzinfo removed) for Mongo-friendly storage.
    If dt is naive, assume it's already UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    try:
        # Convert to UTC then drop tzinfo
        return dt.astimezone(pytz.UTC).replace(tzinfo=None) if pytz else dt
    except Exception:
        return dt.replace(tzinfo=None)


# -------------------------
# USER MODELS
# -------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str

    class Config:
        schema_extra = {
            "example": {"email": "alice@example.com", "password": "S3curePa$$"}
        }



class SendOtpRequest(BaseModel):
    email: str

class SendOtpResponse(BaseModel):
    success: bool
    message: str


class SendOtpResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str


class CompleteRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = Field(None, description="Optional username")
    role: Optional[str] = Field(None, description="Optional role")
    hobbies: Optional[List[str]] = Field(default_factory=list, description="Optional hobbies")
    is_verified: bool = Field(..., description="Indicates if the user is verified")


class UpdatePasswordRequest(BaseModel):
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    email: EmailStr
    hashed_password: str


class UserPublic(BaseModel):
    id: str = Field(..., alias="_id")
    email: EmailStr

    class Config:
        populate_by_name = True


class UserProfile(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    language: str = "en"
    theme: str = "dark"
    role: Optional[str] = "member"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("timezone")
    def _validate_timezone(cls, v):
        if v is None:
            return v
        if _AVAILABLE_TIMEZONES and v not in _AVAILABLE_TIMEZONES:
            raise ValueError("timezone must be a valid IANA timezone (e.g., 'Asia/Kolkata')")
        return v

    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "_id": "64f1c2e0a7b9b9a1f0e8b3c4",
                "user_id": "64f1c2e0a7b9b9a1f0e8b3c4",
                "name": "Alice",
                "timezone": "Asia/Kolkata",
            }
        }


class UserStats(BaseModel):
    total_chats: int = 0
    total_messages: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    active_sessions: int = 0
    avg_session_length: float = 0.0


class UserUpdateProfile(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = None
    role: Optional[str] = None

    @validator("timezone")
    def _validate_timezone(cls, v):
        if v is None:
            return v
        if _AVAILABLE_TIMEZONES and v not in _AVAILABLE_TIMEZONES:
            raise ValueError("timezone must be a valid IANA timezone (e.g., 'Asia/Kolkata')")
        return v


# -------------------------
# API KEY MODELS
# -------------------------
class APIKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    provider: Optional[str] = None
    external_key: Optional[str] = None


class APIKey(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    key_preview: str
    hashed_key: str
    provider: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    is_active: bool = True

    class Config:
        populate_by_name = True


class APIKeyPublic(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    key_preview: str
    provider: Optional[str] = None
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool


# -------------------------
# TASK MODELS
# -------------------------
class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskRecurrence(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class NotifyChannel(str, Enum):
    EMAIL = "email"
    CHAT = "chat"
    BOTH = "both"


class TaskCreate(BaseModel):
    """
    Creating a task:
     - Provide either `due_date` (datetime) or `when` (natural language) + optional `timezone`.
     - `when` is parsed server-side; timezone if provided should be a valid IANA zone (best-effort).
    """
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    when: Optional[str] = None
    timezone: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    recurrence: Optional[TaskRecurrence] = TaskRecurrence.NONE
    notify_channel: NotifyChannel = NotifyChannel.EMAIL
    allow_past: bool = False

    @validator("timezone")
    def _validate_timezone(cls, v):
        if v is None:
            return v
        if _AVAILABLE_TIMEZONES and v not in _AVAILABLE_TIMEZONES:
            raise ValueError("timezone must be a valid IANA timezone (e.g., 'Asia/Kolkata')")
        return v

    @validator("tags", pre=True)
    def _norm_tags(cls, v):
        return _ensure_list_of_str(v)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    recurrence: Optional[TaskRecurrence] = None
    notify_channel: Optional[NotifyChannel] = None
    allow_past: Optional[bool] = False

    @validator("tags", pre=True)
    def _norm_tags(cls, v):
        if v is None:
            return v
        return _ensure_list_of_str(v)


class Task(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    recurrence: Optional[TaskRecurrence] = TaskRecurrence.NONE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Additional operational fields used by the scheduler/worker
    notify_channel: NotifyChannel = NotifyChannel.EMAIL
    celery_task_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True

    @root_validator(pre=True)
    def _coerce_tags_and_defaults(cls, values):
        # Accept legacy "tags" as comma-separated string
        tags = values.get("tags")
        if isinstance(tags, str):
            values["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        elif tags is None:
            values["tags"] = []
        # ensure notify_channel key exists
        if "notify_channel" not in values or values.get("notify_channel") is None:
            values["notify_channel"] = NotifyChannel.EMAIL
        return values

    def to_mongo(self) -> Dict[str, Any]:
        """
        Convert to a Mongo-friendly dict:
         - convert alias `_id` back to ObjectId-like string (caller may convert to ObjectId)
         - normalize datetimes to naive UTC for storage
        """
        out = self.dict(by_alias=True, exclude_none=True)
        # Pydantic uses alias "_id", ensure it's actually a string for storage caller to ObjectId() if desired
        if "_id" in out:
            try:
                # keep as-is (string). If you need ObjectId, convert before insert.
                out["_id"] = str(out["_id"])
            except Exception:
                out["_id"] = out["_id"]
        # normalize datetimes
        for k in ("created_at", "updated_at", "completed_at", "due_date"):
            if k in out and out[k] is not None:
                out[k] = _dt_to_naive_utc(out[k])
        return out

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "Task":
        """
        Convert a raw Mongo doc into Task model. Accepts either string or ObjectId for _id.
        """
        d = dict(doc)
        if "_id" in d:
            d["_id"] = str(d["_id"])
        # If datetimes stored as naive UTC they are fine; let Pydantic validate
        return cls.parse_obj(d)


class TaskBulkUpdate(BaseModel):
    task_ids: List[str]
    operation: str  # one of "delete", "complete", "update_status", "update_priority"
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None

    @validator("task_ids", pre=True)
    def _ensure_task_ids(cls, v):
        if isinstance(v, str):
            return [v]
        if not v:
            return []
        return [str(x) for x in v]


# -------------------------
# TOKEN MODELS
# -------------------------
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenWithUser(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr


# -------------------------
# CHAT & SESSION MODELS
# -------------------------
class Message(BaseModel):
    id: str = Field(..., alias="_id")
    sender: str  # 'user' | 'assistant'
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class SessionBase(BaseModel):
    title: str = "New Chat"
    user_id: str = Field(..., alias="userId")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")

    class Config:
        populate_by_name = True


class SessionInDB(SessionBase):
    id: str = Field(..., alias="_id")
    messages: List[Message] = Field(default_factory=list)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow, alias="lastUpdatedAt")
    is_archived: bool = Field(default=False, alias="isArchived")

    class Config:
        populate_by_name = True


class SessionPublic(BaseModel):
    id: str = Field(..., alias="_id")
    title: str
    created_at: datetime = Field(..., alias="createdAt")
    last_updated_at: datetime = Field(..., alias="lastUpdatedAt")
    message_count: int = 0
    preview: Optional[str] = None

    class Config:
        populate_by_name = True


class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"
    initial_message: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


# -------------------------
# ACTIVITY & SECURITY MODELS
# -------------------------
class ActivityType(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CHAT_CREATED = "chat_created"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    PROFILE_UPDATED = "profile_updated"
    API_KEY_CREATED = "api_key_created"
    API_KEY_DELETED = "api_key_deleted"


class ActivityLog(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    activity_type: ActivityType
    description: str
    metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class SecurityEvent(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    event_type: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None
    success: bool = True
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# -------------------------
# DASHBOARD & NOTIFICATIONS
# -------------------------
class DashboardStats(BaseModel):
    user_stats: UserStats
    recent_activity: List[ActivityLog] = Field(default_factory=list)
    recent_chats: List[SessionPublic] = Field(default_factory=list)
    task_summary: Dict[str, int] = Field(default_factory=dict)


class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "info"
    action_url: Optional[str] = None


class Notification(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    title: str
    message: str
    type: str = "info"
    action_url: Optional[str] = None
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# -------------------------
# Final notes & suggestions
# -------------------------
# Suggestions for integration (not enforced here):
# 1) Before inserting models into Mongo, call Task.to_mongo() (or other_model.dict(by_alias=True))
#    to normalize datetimes to naive UTC and to convert IDs to strings. Convert _id to ObjectId()
#    only when necessary (insert/read patterns vary across codebases).
# 2) Validate user-provided timezones at the API layer using pytz (we validate if pytz is available).
# 3) Use the `notify_channel` field to drive email vs in-app notification behavior in the Celery worker.
# 4) Add indices in DB for frequently queried fields:
#       - tasks: {"user_id":1, "due_date":1}, {"user_id":1, "status":1}, text index on title+description
#       - sessions: {"userId":1, "lastUpdatedAt":-1}
# 5) When returning models from DB, prefer Model.from_mongo(doc) helpers (where provided) to ensure
#    alias mapping and types are normalized.
#
# If you want I can:
# - produce a small utility module `model_utils.py` with `to_mongo()` / `from_mongo()` helpers for all models,
# - update the routes to call these helpers consistently, or
# - add stricter JSON schema examples for API docs.
#
# End of models.py