# backend/app/models.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

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
    sender: str
    text: str


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

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
