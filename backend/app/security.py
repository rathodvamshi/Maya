# backend/app/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.collection import Collection

from app.config import settings
from app.database import get_user_collection


# ======================================================
# PASSWORD HASHING
# ======================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plain password for secure storage."""
    return pwd_context.hash(password)


# ======================================================
# JWT TOKEN HANDLING
# ======================================================

class TokenData(BaseModel):
    """Model for storing token payload data."""
    username: Optional[str] = None


def create_access_token(data: dict) -> str:
    """Generate an access token with expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Generate a refresh token with expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str, credentials_exception) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return TokenData(username=username)
    except JWTError:
        raise credentials_exception


# ======================================================
# FASTAPI SECURITY DEPENDENCIES
# ======================================================

# Define OAuth2 scheme for FastAPI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_active_user(
    token: str = Depends(oauth2_scheme),
    users_collection: Collection = Depends(get_user_collection)
) -> dict:
    """
    Dependency to get the current active user from the database.
    - Decodes the JWT token.
    - Fetches the user from MongoDB based on the email in the token.
    - Raises 401 if the token is invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_token(token, credentials_exception)

    user = users_collection.find_one({"email": token_data.username})
    if user is None:
        raise credentials_exception

    # Convert ObjectId to string for easier use
    user["_id"] = str(user["_id"])
    return user
