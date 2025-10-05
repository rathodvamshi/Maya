# backend/app/models.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ======================================================
# USER MODELS
# ======================================================

class UserCreate(BaseModel):
    """
    Model for creating a new user.
    Expects:
        - email: User's email address
        - password: Plain-text password (will be hashed before storage)
    """
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    """
    Internal model representing a user stored in the database.
    Includes hashed password for authentication.
    """
    email: EmailStr
    hashed_password: str


class UserPublic(BaseModel):
    """
    Model for exposing safe user information to clients.
    Excludes sensitive data like hashed_password.
    """
    id: str
    email: EmailStr


class UserProfile(BaseModel):
    """
    Extended user profile information.
    """
    id: str = Field(..., alias="_id")
    user_id: str
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    language: str = "en"
    theme: str = "dark"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


class UserStats(BaseModel):
    """
    User statistics for dashboard.
    """
    total_chats: int = 0
    total_messages: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    active_sessions: int = 0
    avg_session_length: float = 0.0


class UserUpdateProfile(BaseModel):
    """
    Model for updating user profile.
    """
    name: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = None


# ======================================================
# API KEY MODELS
# ======================================================

class APIKeyCreate(BaseModel):
    """
    Model for creating a new API key.
    """
    name: str
    description: Optional[str] = None


class APIKey(BaseModel):
    """
    Model for API key stored in database.
    """
    id: str = Field(..., alias="_id")
    user_id: str
    name: str
    description: Optional[str] = None
    key_preview: str  # First 8 characters + "..."
    hashed_key: str   # Full hashed key for verification
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    is_active: bool = True
    
    class Config:
        populate_by_name = True


class APIKeyPublic(BaseModel):
    """
    Public API key model (without sensitive data).
    """
    id: str
    name: str
    description: Optional[str] = None
    key_preview: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool


# ======================================================
# TASK MODELS
# ======================================================

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


class TaskCreate(BaseModel):
    """
    Model for creating a new task.
    """
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    """
    Model for updating a task.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None


class Task(BaseModel):
    """
    Complete task model.
    """
    id: str = Field(..., alias="_id")
    user_id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


class TaskBulkUpdate(BaseModel):
    """
    Model for bulk task operations.
    """
    task_ids: List[str]
    operation: str  # "delete", "complete", "update_status", "update_priority"
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None


# ======================================================
# TOKEN MODELS
# ======================================================

class Token(BaseModel):
    """
    Model for JWT tokens returned on login.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    """
    Model for refreshing access tokens using a valid refresh token.
    """
    refresh_token: str


class TokenWithUser(BaseModel):
    """
    Login response including tokens plus user identity info.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr


# ======================================================
# CHAT & SESSION MODELS
# ======================================================

class Message(BaseModel):
    """
    Model for a single message within a chat session.
    sender: 'user' or 'assistant'
    text: message content
    """
    id: str = Field(default_factory=lambda: str(ObjectId()))
    sender: str
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class SessionBase(BaseModel):
    """
    Base model for a chat session.
    Used for creating new sessions and listing basic session info.
    """
    title: str
    user_id: str = Field(..., alias="userId")  # Links session to a specific user
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")

    class Config:
        populate_by_name = True  # Allow population using alias names
        arbitrary_types_allowed = True


class SessionInDB(SessionBase):
    """
    Model representing a session stored in the database.
    Includes full messages, last update timestamp, and archive status.
    """
    id: str = Field(..., alias="_id")
    messages: List[Message] = Field(default_factory=list)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow, alias="lastUpdatedAt")
    is_archived: bool = Field(default=False, alias="isArchived")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class SessionPublic(BaseModel):
    """
    Public-facing model for listing sessions.
    Only includes safe and minimal info.
    """
    id: str
    title: str
    created_at: datetime = Field(..., alias="createdAt")
    last_updated_at: datetime = Field(..., alias="lastUpdatedAt")
    message_count: int = 0
    preview: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class SessionCreate(BaseModel):
    """
    Model for creating a new session.
    """
    title: Optional[str] = "New Chat"
    initial_message: Optional[str] = None


class SessionUpdate(BaseModel):
    """
    Model for updating session metadata.
    """
    title: Optional[str] = None
    is_archived: Optional[bool] = None


# ======================================================
# ACTIVITY & SECURITY MODELS
# ======================================================

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
    """
    User activity log entry.
    """
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
    """
    Security event log entry.
    """
    id: str = Field(..., alias="_id")
    user_id: str
    event_type: str  # "login_success", "login_failed", "suspicious_activity", etc.
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None
    success: bool = True
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


# ======================================================
# DASHBOARD MODELS
# ======================================================

class DashboardStats(BaseModel):
    """
    Dashboard statistics overview.
    """
    user_stats: UserStats
    recent_activity: List[ActivityLog]
    recent_chats: List[SessionPublic]
    task_summary: Dict[str, int]
    
    
class NotificationCreate(BaseModel):
    """
    Model for creating notifications.
    """
    title: str
    message: str
    type: str = "info"  # "info", "success", "warning", "error"
    action_url: Optional[str] = None


class Notification(BaseModel):
    """
    User notification model.
    """
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


# Import ObjectId for default generation
from bson import ObjectId
