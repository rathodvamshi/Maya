"""
app/routes/auth.py
def verify_otp(payload: VerifyOtpRequest):
Unified authentication module:
- /api/auth/* endpoints (OTP, registration, login, refresh, update password, user info)
- Legacy /auth/* endpoints pointing to same logic
- Supports Redis and Mongo OTP storage
- Handles background email sending
- Logging, duplicate checks, JWT token
"""

import random
import string
import logging
from datetime import datetime, timedelta
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from fastapi.security import OAuth2PasswordRequestForm

from pymongo.errors import DuplicateKeyError
from pymongo.collection import Collection

# Project imports - adjust according to your project structure
from app.database import get_user_collection, db_client
from app.logger import logger
from app.otp import redis_client
from app.database import get_email_otps_collection
from app.utils.email_utils import send_otp_email, send_welcome_email, EmailSendError
from app.security import get_password_hash, verify_password, create_access_token, create_refresh_token, get_current_active_user, verify_token

# ---- Pydantic models ----
def _otp_coll():
    return get_email_otps_collection()
class SendOtpRequest(BaseModel):
    email: EmailStr

class SendOtpResponse(BaseModel):
    success: bool = True
    message: str
    expires_in: int | None = None
    email: EmailStr | None = None

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str

class CompleteRegistrationRequest(BaseModel):
    email: EmailStr
    otp: str | None = None
    password: str
    username: str | None = None
    role: str | None = None
    hobbies: list[str] | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UpdatePasswordRequest(BaseModel):
    email: EmailStr
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

class UpdateMeRequest(BaseModel):
    username: str | None = None
    role: str | None = None
    hobbies: list[str] | None = None

# ---- Router setup ----
api_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
legacy_router = APIRouter(prefix="/auth", tags=["Authentication"])

# Export for main.py
router = api_router

# ---- Constants ----
OTP_TTL_SECONDS = 300
VERIFIED_TTL_SECONDS = 600

# ---- Helpers ----
def _gen_otp(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


async def is_otp_verified_for_email(email: str) -> bool:
    coll = _otp_coll()
    try:
        rec = coll.find_one({"email": email, "verified": True})
        logger.info(f"Checking OTP verified status for email: {email}, found record: {rec}")
        if rec:
            return True
    except Exception as exc:
        logger.warning("Mongo check verified failed for %s: %s", email, exc)
    # Fallback to Redis flag
    try:
        val = await redis_client.get(f"verified:{email}")
        return (val == "1") or (val == b"1")
    except Exception as exc:
        logger.warning("Redis check verified failed for %s: %s", email, exc)
    logger.warning(f"OTP not verified for email: {email}")
    return False

# ---- API Endpoints ----


# --- Send OTP ---
@api_router.post("/send-otp", response_model=SendOtpResponse)
async def send_otp(payload: SendOtpRequest, background_tasks: BackgroundTasks):
    email = payload.email.lower().strip()
    otp_code = _gen_otp(4)
    coll = _otp_coll()
    wrote_to_mongo = False
    try:
        coll.update_one(
            {"email": email},
            {"$set": {"email": email, "otp": otp_code, "expires_at": datetime.utcnow() + timedelta(seconds=OTP_TTL_SECONDS), "verified": False}},
            upsert=True
        )
        coll.create_index("expires_at", expireAfterSeconds=0)
        wrote_to_mongo = True
    except Exception as exc:
        logger.warning("Falling back to Redis for OTP send for %s: %s", email, exc)
        try:
            # Store OTP with TTL
            await redis_client.setex(f"otp:{email}", OTP_TTL_SECONDS, otp_code)
        except Exception as r_exc:
            logger.error("Failed to store OTP in Redis for %s: %s", email, r_exc)
            raise HTTPException(status_code=503, detail="OTP service unavailable")
    def _send_email_task(e, code):
        try:
            send_otp_email(e, code)
        except Exception as exc:
            logger.error("OTP email failed for %s: %s", e, exc)
    background_tasks.add_task(_send_email_task, email, otp_code)
    return SendOtpResponse(success=True, message="OTP generated and email enqueued", expires_in=OTP_TTL_SECONDS, email=email)


@api_router.post("/verify-otp")
async def verify_otp(payload: VerifyOtpRequest):
    email = payload.email.lower().strip()
    otp_entered = payload.otp.strip()
    logger.info(f"OTP verification requested for email: {email}, OTP entered: {otp_entered}")
    coll = _otp_coll()
    rec = None
    try:
        rec = coll.find_one({"email": email})
        logger.info(f"OTP record found: {rec}")
    except Exception as exc:
        logger.warning("Mongo read failed during verify for %s: %s", email, exc)
    if not rec:
        # Fallback: check Redis
        try:
            stored = await redis_client.get(f"otp:{email}")
            if not stored:
                logger.error(f"No OTP record found for email: {email}")
                raise HTTPException(status_code=400, detail="No OTP record found for this email")
            if (stored if isinstance(stored, str) else stored.decode()) != otp_entered:
                logger.error(f"OTP mismatch for email: {email} (redis)")
                raise HTTPException(status_code=400, detail="Incorrect OTP")
            # Mark verified in Redis
            await redis_client.setex(f"verified:{email}", VERIFIED_TTL_SECONDS, "1")
            # Clear the OTP key
            try:
                await redis_client.delete(f"otp:{email}")
            except Exception:
                pass
            return {"message": "OTP verified successfully", "is_verified": True}
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Redis verify failed for %s: %s", email, exc)
            raise HTTPException(status_code=503, detail="OTP verification unavailable")
    # Validate against Mongo record
    if rec.get("otp") != otp_entered:
        logger.error(f"OTP mismatch for email: {email}. Expected: {rec.get('otp')}, Got: {otp_entered}")
        raise HTTPException(status_code=400, detail="Incorrect OTP")
    if rec.get("expires_at") and rec["expires_at"] < datetime.utcnow():
        logger.error(f"OTP expired for email: {email}")
        raise HTTPException(status_code=400, detail="Expired OTP")
    try:
        result = coll.update_one({"email": email}, {"$set": {"verified": True}})
        logger.info(f"OTP verification update result: modified_count={result.modified_count}")
    except Exception as exc:
        logger.warning("Mongo write failed marking verified for %s: %s; falling back to Redis flag", email, exc)
        try:
            await redis_client.setex(f"verified:{email}", VERIFIED_TTL_SECONDS, "1")
        except Exception as r_exc:
            logger.error("Failed to set verified flag in Redis for %s: %s", email, r_exc)
            raise HTTPException(status_code=503, detail="OTP verification unavailable")
    return {"message": "OTP verified successfully", "is_verified": True}



# --- Complete Registration ---
@api_router.post("/complete-registration")
async def complete_registration(payload: CompleteRegistrationRequest):
    email = payload.email.lower().strip()
    # Ensure Mongo connection if degraded, then get collection
    try:
        if not db_client.healthy():
            db_client.connect()
    except Exception:
        pass
    users = get_user_collection()
    coll = _otp_coll()
    if not await is_otp_verified_for_email(email):
        logger.error(f"Registration failed: OTP not verified for {email}")
        # Debug: show all OTP docs for this email
        all_otp_docs = list(coll.find({"email": email}))
        logger.error(f"All OTP docs for {email}: {all_otp_docs}")
        raise HTTPException(status_code=400, detail="OTP not verified. Please verify your OTP before registering.")
    existing = users.find_one({"email": email})
    if existing:
        logger.error(f"Registration failed: Email already registered {email}")
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed = get_password_hash(payload.password)
    user_doc = {
        "email": email,
        "password": hashed,
        "username": payload.username or "",
        "role": payload.role or "",
        "hobbies": payload.hobbies or [],
        "created_at": datetime.utcnow(),
        "is_verified": True,
    }
    try:
        result = users.insert_one(user_doc)
    except Exception as exc:
        # Attempt one reconnect and retry insert if DB was degraded
        try:
            if not db_client.healthy():
                db_client.connect()
            users_retry = get_user_collection()
            result = users_retry.insert_one(user_doc)
        except Exception:
            logger.error("User insert failed for %s: %s", email, exc)
            raise HTTPException(status_code=503, detail="Database unavailable. Please try again shortly.")
    # Delete OTP doc after registration (best-effort) and clear Redis flags
    try:
        coll.delete_one({"email": email})
    except Exception:
        pass
    try:
        await redis_client.delete(f"otp:{email}")
        await redis_client.delete(f"verified:{email}")
    except Exception:
        pass
    try:
        send_welcome_email(email)
    except Exception as e:
        logger.error(f"Welcome email failed for {email}: {e}")
    access_token = create_access_token({"sub": email, "user_id": str(result.inserted_id)})
    logger.info(f"User registered successfully: {email}")
    return JSONResponse(status_code=201, content={"message": "User registered successfully", "user_id": str(result.inserted_id), "access_token": access_token, "token_type": "bearer", "email": email})

# --- Register (start OTP flow) ---

@api_router.post("/register")
def register(payload: SendOtpRequest):
    users = get_user_collection()
    existing = users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    otp_code = _gen_otp(4)
    coll = _otp_coll()
    coll.update_one(
        {"email": payload.email},
        {"$set": {"email": payload.email, "otp": otp_code, "expires_at": datetime.utcnow() + timedelta(minutes=5), "verified": False}},
        upsert=True
    )
    coll.create_index("expires_at", expireAfterSeconds=0)
    try:
        send_otp_email(payload.email, otp_code)
    except Exception:
        pass
    return {"message": "OTP sent to email", "expires_in": 300, "email": payload.email}

# --- Login ---

@api_router.post("/login")

async def login(payload: LoginRequest):
    try:
        users = get_user_collection()
        user = users.find_one({"email": payload.email.lower()})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if "password" not in user:
            raise HTTPException(status_code=500, detail="User record missing password field")
        if not verify_password(payload.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if "email" not in user or "_id" not in user:
            raise HTTPException(status_code=500, detail="User record missing required fields")
        token = create_access_token({"sub": user["email"], "user_id": str(user["_id"])});
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        print("Login error:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Current user info ---

@api_router.get("/me")
def whoami(current_user: dict = Depends(get_current_active_user)):
    """Return current user basics sourced from the users collection.

    Includes username when available to support UI displays that prefer a handle.
    """
    return {
        "user_id": str(current_user["_id"]),
        "email": current_user.get("email"),
        "username": current_user.get("username", ""),
        "role": current_user.get("role", ""),
        "hobbies": current_user.get("hobbies", []),
        "profile": current_user.get("profile", {}),
    }

@api_router.patch("/me")
def update_me(payload: UpdateMeRequest, current_user: dict = Depends(get_current_active_user)):
    """Update current user's core fields in the users collection.

    Allows updating: username, role, hobbies.
    Returns the updated basics payload similar to GET /me.
    """
    users = get_user_collection()
    updates: dict = {}
    if payload.username is not None:
        updates["username"] = payload.username
    if payload.role is not None:
        updates["role"] = payload.role
    if payload.hobbies is not None:
        # Ensure list of strings
        if not isinstance(payload.hobbies, list):
            raise HTTPException(status_code=400, detail="hobbies must be a list of strings")
        updates["hobbies"] = [str(h).strip() for h in payload.hobbies if str(h).strip()]
    if not updates:
        # Nothing to update; return current snapshot
        return whoami(current_user)
    try:
        users.update_one({"_id": current_user["_id"]}, {"$set": updates})
    except Exception as exc:
        logger.error("Failed to update user core fields: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update user")
    # Re-read (best-effort)
    fresh = users.find_one({"_id": current_user["_id"]}) or current_user
    return {
        "user_id": str(fresh["_id"]),
        "email": fresh.get("email"),
        "username": fresh.get("username", ""),
        "role": fresh.get("role", ""),
        "hobbies": fresh.get("hobbies", []),
        "profile": fresh.get("profile", {}),
    }

# --- Refresh JWT token ---

@api_router.post("/refresh")
def refresh(payload: TokenRefresh):
    cred_exc = HTTPException(status_code=401, detail="Invalid refresh token")
    token_data = None
    try:
        token_data = verify_token(payload.refresh_token, cred_exc)
    except HTTPException:
        raise cred_exc
    users = get_user_collection()
    user = users.find_one({"email": token_data.username})
    if not user:
        raise cred_exc
    new_token = create_access_token({"sub": user["email"], "user_id": str(user["_id"])});
    return {"access_token": new_token, "refresh_token": payload.refresh_token, "token_type": "bearer"}

# --- Update / reset password ---

@api_router.post("/update-password")
def update_password(payload: UpdatePasswordRequest):
    coll = _otp_coll()
    rec = coll.find_one({"email": payload.email, "verified": True})
    if not rec:
        raise HTTPException(status_code=400, detail="OTP not verified")
    users = get_user_collection()
    hashed_password = get_password_hash(payload.password)
    user = users.find_one({"email": payload.email})
    if user:
        users.update_one({"_id": user["_id"]}, {"$set": {"password": hashed_password}})
        user_id = str(user["_id"])
    else:
        result = users.insert_one({"email": payload.email, "password": hashed_password, "created_at": datetime.utcnow()})
        user_id = str(result.inserted_id)
    coll.delete_one({"email": payload.email})
    return {"status": "ok", "user_id": user_id}

# --- Email availability ---

@api_router.get("/email-available")
def email_available(email: str):
    users = get_user_collection()
    exists = users.find_one({"email": email}) is not None
    return {"available": not exists}

# ---- Legacy /auth/* endpoints pointing to same logic ----
legacy_router.post("/send-otp")(send_otp)
legacy_router.post("/verify-otp")(verify_otp)
legacy_router.post("/complete-registration")(complete_registration)
legacy_router.post("/register")(register)
legacy_router.post("/login")(login)
legacy_router.get("/me")(whoami)
legacy_router.patch("/me")(update_me)
legacy_router.post("/refresh")(refresh)
legacy_router.post("/update-password")(update_password)
legacy_router.get("/email-available")(email_available)
