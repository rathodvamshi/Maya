
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from datetime import datetime
from app.security import get_current_active_user
from app.database import get_user_collection
from app.services.neo4j_service import neo4j_service
from app.services import redis_service
from app.config import settings
from app.services import profile_service
import random
import smtplib
from email.mime.text import MIMEText


# Public endpoints (no auth required)
public_router = APIRouter(prefix="/api/user", tags=["User"])

# Protected endpoints (require auth)
router = APIRouter(prefix="/api/user", tags=["User"], dependencies=[Depends(get_current_active_user)])

class EmailCheckRequest(BaseModel):
    email: str

@public_router.get("/check-email")
async def check_email_exists(email: str = Query(...), users: Collection = Depends(get_user_collection)):
    # Check if email exists in user collection
    exists = users.find_one({"email": email}) is not None
    return {"available": not exists}

# --- OTP Email Verification ---
def generate_otp():
    return str(random.randint(1000, 9999))

def send_otp_email(email: str, otp: str):
    # Example using SMTP (replace with your config)
    import threading
    # Use settings from config.py
    smtp_host = settings.MAIL_SERVER
    smtp_port = settings.MAIL_PORT
    smtp_user = settings.MAIL_USERNAME
    smtp_pass = settings.MAIL_PASSWORD
    mail_from = settings.MAIL_FROM
    starttls = settings.MAIL_STARTTLS
    ssl_tls = settings.MAIL_SSL_TLS
    # Validate config
    if not smtp_user or not smtp_pass or not mail_from:
        raise RuntimeError("MAIL_USERNAME, MAIL_PASSWORD, or MAIL_FROM not set. Please set Gmail app password and sender email in .env.")
    msg = MIMEText(f'Your verification code is {otp}. It expires in 5 minutes.')
    msg['Subject'] = 'Your Signup OTP'
    msg['From'] = mail_from
    msg['To'] = email
    result = {'success': False, 'error': None}
    def send():
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if starttls:
                    server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(mail_from, [email], msg.as_string())
            print(f"OTP email sent to {email}")
            result['success'] = True
        except Exception as e:
            print(f"Failed to send OTP email to {email}: {e}")
            result['error'] = str(e)
    t = threading.Thread(target=send, daemon=True)
    t.start()
    t.join(timeout=15)
    return result

@public_router.post("/send-otp")
async def send_otp(email: str):
    otp = generate_otp()
    # Store OTP in Redis with expiry (5 min)
    await redis_service.redis_client.set(f"otp:{email}", otp, ex=300)
    try:
        email_result = send_otp_email(email, otp)
    except Exception as e:
        return {"success": False, "message": str(e)}
    if not email_result or not email_result.get('success'):
        err_msg = email_result['error'] if isinstance(email_result, dict) and 'error' in email_result else 'Unknown error'
        return {"success": False, "message": f"Failed to send OTP email: {err_msg}"}
    return {"success": True, "message": "OTP sent"}
# Health check endpoint for email config
@public_router.get("/email-health")
async def email_health():
    import os
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    if not smtp_user or not smtp_pass:
        return {"ok": False, "error": "SMTP_USER or SMTP_PASS not set. Please set Gmail app password."}
    return {"ok": True, "user": smtp_user}

@public_router.post("/verify-otp")
async def verify_otp(email: str, otp: str):
    stored_otp = await redis_service.redis_client.get(f"otp:{email}")
    if not stored_otp:
        return {"verified": False, "error": "OTP expired or not found"}
    if otp == (stored_otp.decode() if isinstance(stored_otp, bytes) else stored_otp):
        await redis_service.redis_client.delete(f"otp:{email}")
        return {"verified": True}
    else:
        return {"verified": False, "error": "OTP invalid"}

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from datetime import datetime
from app.security import get_current_active_user
from app.database import get_user_collection
from app.services.neo4j_service import neo4j_service
from app.services import redis_service
from app.services import profile_service
import random
import smtplib
from email.mime.text import MIMEText

router = APIRouter(prefix="/api/user", tags=["User"], dependencies=[Depends(get_current_active_user)])

class EmailCheckRequest(BaseModel):
    email: str

# Removed duplicate protected check-email route; use public_router.get("/check-email") only.

## Removed duplicate/legacy OTP email and verification code blocks. Use public_router endpoints and environment-based SMTP config only.


class OnboardingBody(BaseModel):
    name: str | None = None
    region: str | None = None
    preferences: dict | None = None


@router.get("/onboarding-questions")
async def onboarding_questions():
    return {
        "questions": [
            {"id": "name", "q": "What's your preferred name?"},
            {"id": "region", "q": "Which region/country are you in?"},
            {"id": "cuisine", "q": "Any favorite cuisine?"},
        ]
    }


@router.post("/onboarding")
async def onboarding(
    body: OnboardingBody,
    current_user: dict = Depends(get_current_active_user),
    users: Collection = Depends(get_user_collection),
):
    # Update Mongo profile
    profile_update = {k: v for k, v in body.model_dump().items() if v is not None}
    users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"profile": profile_update, "last_seen": datetime.utcnow()}},
    )

    user_id = str(current_user["_id"])
    # Update Neo4j (best-effort), create preferences relations
    try:
        await neo4j_service.create_user_node(user_id)
        if body.name:
            await neo4j_service.run_query(
                "MERGE (u:User {id: $uid}) SET u.name=$name",
                {"uid": user_id, "name": body.name},
            )
        prefs = body.preferences or {}
        for k, v in prefs.items():
            if not v:
                continue
            await neo4j_service.run_query(
                "MERGE (u:User {id:$uid})\n MERGE (p:PREFERENCE {name:$val})\n MERGE (u)-[:LIKES {kind:$kind}]->(p)",
                {"uid": user_id, "val": str(v), "kind": k},
            )
    except Exception:
        pass

    # Cache small profile in Redis for quick personalization
    try:
        cache_key = f"user:{user_id}:recent_profile"
        await redis_service.set_prefetched_data(cache_key, profile_update or {}, ttl_seconds=300)
    except Exception:
        pass

    greeting = f"Welcome {body.name}!" if body.name else "Welcome!"
    return {"status": "ok", "greeting": greeting}


# ---------------- Preferences API ----------------
_TONE_MAP = {
    "fun": "playful",
    "playful": "playful",
    "formal": "formal",
    "neutral": "neutral",
    "supportive": "supportive",
    "enthusiastic": "enthusiastic",
}


class PreferencesBody(BaseModel):
    enable_emojis: bool | None = Field(default=None, description="If true, enable emoji enrichment")
    enable_emotion_persona: bool | None = Field(default=None, description="If false, disable persona overlay")
    tone: str | None = Field(default=None, description="Tone preference e.g. fun/playful/formal/neutral")


@router.post("/preferences")
async def set_preferences(body: PreferencesBody, current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    updates: dict[str, str] = {}
    updated: dict[str, str] = {}
    # Normalize booleans to on/off strings as stored preference values
    if body.enable_emojis is not None:
        updates["emoji"] = "on" if body.enable_emojis else "off"
        updated["emoji"] = updates["emoji"]
    if body.enable_emotion_persona is not None:
        updates["emotion_persona"] = "on" if body.enable_emotion_persona else "off"
        updated["emotion_persona"] = updates["emotion_persona"]
    if body.tone is not None:
        tone_raw = (body.tone or "").strip().lower()
        tone_norm = _TONE_MAP.get(tone_raw)
        if not tone_norm:
            raise HTTPException(status_code=400, detail="Invalid tone")
        updates["tone"] = tone_norm
        updated["tone"] = tone_norm

    if not updates:
        # No changes; return current effective
        prof = profile_service.get_profile(user_id)
        effective = prof.get("preferences", {})
        return {"updated": {}, "effective": effective}

    prof = profile_service.merge_update(user_id, add_preferences=updates)
    return {"updated": updated, "effective": prof.get("preferences", {})}


@router.get("/preferences")
async def get_preferences(current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    prof = profile_service.get_profile(user_id)
    # Effective simply returns stored preferences; future: blend with inferred
    return {"effective": prof.get("preferences", {})}
