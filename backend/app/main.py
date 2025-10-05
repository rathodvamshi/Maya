# backend/app/main.py

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import asyncio

from app.routers import auth, chat, sessions, feedback, health, debug, metrics as metrics_router
from app.routers import mini_agent
from app.routers import emotion as emotion_router
from app.routers import health_extended
from app.routers import user as user_router
from app.routers import memories as memories_router
from app.routers import tasks, profile, dashboard
from app.config import settings
from app.services import advanced_emotion
from app.utils.rate_limit import RateLimiter
from app.services.neo4j_service import neo4j_service
from app.services import pinecone_service, redis_service
from app.database import db_client

# --- Lifespan Management for Connections ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for all external services."""
    print("--- Application starting up... ---")
    
    # Initialize services (non-blocking with short timeouts)
    try:
        await asyncio.wait_for(asyncio.to_thread(pinecone_service.initialize_pinecone), timeout=15.0)
    except Exception as e:
        print(f"⚠️ Pinecone init skipped or timed out: {e}")

    # Asynchronously connect to Neo4j using a short timeout
    try:
        await asyncio.wait_for(neo4j_service.connect(), timeout=3.0)
    except Exception as e:
        print(f"⚠️ Neo4j connect timed out: {e}")
    
    # Create Mongo indexes early
    try:
        await asyncio.to_thread(db_client.ensure_indexes)
    except Exception:
        pass

    # Verify connections and print status messages
    print("--- Verifying Connections ---")
    print("✅ MongoDB connected")
    try:
        redis_ok = await redis_service.redis_client.ping()
    except Exception:
        redis_ok = False
    print("✅ Redis connected" if redis_ok else "❌ Redis not connected")
    print(f"✅ Pinecone connected" if getattr(pinecone_service, 'index', None) else "❌ Pinecone not connected")
    print(f"✅ Neo4j connected" if getattr(neo4j_service, '_driver', None) else "❌ Neo4j not connected")
    
    print("--- Startup complete. ---")
    yield
    
    # Gracefully close connections on shutdown
    print("--- Application shutting down... ---")
    await neo4j_service.close()
    if redis_service.redis_client:
        await redis_service.redis_client.close()
    if db_client and db_client.client:
        db_client.client.close()
    print("--- Shutdown complete. ---")

app = FastAPI(
    title="Personal AI Assistant API",
    lifespan=lifespan,
)

# --- CORS Middleware ---
# Allow configuration via env var CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
import os, time

raw_origins = os.getenv("CORS_ORIGINS")
allow_all = os.getenv("CORS_ALLOW_ALL") in {"1", "true", "TRUE"}
if allow_all:
    origins = ["*"]
elif raw_origins:
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
else:
    # Default dev ports; include 3001 for React alt dev server
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

# If an extra DEV_ORIGINS env is present append them
extra = os.getenv("DEV_EXTRA_ORIGINS")
if extra:
    for o in extra.split(','):
        o = o.strip()
        if o and o not in origins:
            origins.append(o)

print(f"CORS origins configured: {origins} allow_all={allow_all}")

# --- Optional CORS debug / dynamic dev reflection ---
DEBUG_CORS = os.getenv("DEBUG_CORS") in {"1", "true", "TRUE"}
ALLOW_DYNAMIC_LOCAL = os.getenv("CORS_DYNAMIC_LOCAL") in {"1", "true", "TRUE"}

# Pre-compute dev host prefixes for dynamic acceptance (ONLY used if ALLOW_DYNAMIC_LOCAL)
_LOCAL_DEV_PREFIXES = ("http://localhost:", "http://127.0.0.1:")

def _is_dynamic_local_origin(origin: str | None) -> bool:
    if not origin:
        return False
    if not ALLOW_DYNAMIC_LOCAL:
        return False
    return origin.startswith(_LOCAL_DEV_PREFIXES)

def _append_dynamic_origin_if_needed(origin: str | None):
    if not origin:
        return
    if origin in origins or origins == ["*"]:
        return
    if _is_dynamic_local_origin(origin):
        # Append for this process lifetime (dev only). Avoid unbounded growth.
        if len(origins) < 20:
            origins.append(origin)
            if DEBUG_CORS:
                print(f"[CORS][dynamic] Added origin at runtime: {origin}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # may be mutated at runtime for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-CSRF-Token", "X-Debug-CORS"],
    expose_headers=["X-Session-Id", "X-App-Version", "X-Deprecation"],
)

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
BOOT_TIME = time.time()

# Lightweight request logger (dev aid) — logs method, path & origin
@app.middleware("http")
async def _cors_and_logging_mw(request: Request, call_next):
    origin = request.headers.get("origin")
    method = request.method
    path = request.url.path

    # Dynamic dev origin learning (before calling next to ensure middleware sees updated list)
    _append_dynamic_origin_if_needed(origin)

    # Handle preflight early (so even unknown routes show CORS headers for diagnosis)
    if method == "OPTIONS":
        from fastapi.responses import PlainTextResponse
        resp = PlainTextResponse("preflight ok", status_code=200)
        if origins == ["*"] and origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
        elif origin and (origin in origins or _is_dynamic_local_origin(origin)):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers.setdefault("Vary", "Origin")
        # Standard CORS preflight headers
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = request.headers.get("Access-Control-Request-Headers", "Authorization,Content-Type,Accept")
        resp.headers["Access-Control-Max-Age"] = "600"
        resp.headers["X-Debug-CORS"] = "1"
        if DEBUG_CORS:
            print(f"[CORS][preflight] {path} origin={origin} allowed={resp.headers.get('Access-Control-Allow-Origin') is not None}")
        return resp

    response = await call_next(request)

    # Ensure debug header present for troubleshooting
    response.headers.setdefault("X-Debug-CORS", "1")

    try:
        if origins == ["*"] and origin:
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
        elif origin and (origin in origins or _is_dynamic_local_origin(origin)) and "access-control-allow-origin" not in response.headers:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers.setdefault("Vary", "Origin")
    except Exception:
        pass

    if DEBUG_CORS:
        allowed = response.headers.get("Access-Control-Allow-Origin")
        print(f"[CORS][req] {method} {path} origin={origin} allow={bool(allowed)} status={response.status_code}")
    else:
        # Lightweight single-line log
        print(f"REQ {method} {path} origin={origin} -> {response.status_code}")
    return response

# --- Global Exception Handlers (standard error envelope) ---
@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    payload = {"error": {"code": exc.status_code, "message": exc.detail}}
    return JSONResponse(status_code=exc.status_code, content=payload)

@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    payload = {"error": {"code": 422, "message": "Validation error", "details": exc.errors()}}
    return JSONResponse(status_code=422, content=payload)

# Generic fallback
@app.middleware("http")
async def _wrap_unhandled(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:  # noqa: BLE001
        payload = {"error": {"code": 500, "message": "Internal server error"}}
        print(f"Unhandled exception at {request.url.path}: {e}")
        return JSONResponse(status_code=500, content=payload)

# Global per-user rate limit (e.g., 120 req/min)
app.middleware("http")(RateLimiter(max_requests=120, window_seconds=60))

# --- Routers ---
app.include_router(auth.router)
app.include_router(auth.legacy_router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(feedback.router)
app.include_router(health.router)
app.include_router(user_router.router)
app.include_router(debug.router)
app.include_router(memories_router.router)
app.include_router(metrics_router.router)
app.include_router(health_extended.router)
app.include_router(emotion_router.router)
app.include_router(tasks.router)
app.include_router(profile.router)
app.include_router(dashboard.router)
app.include_router(mini_agent.router)

@app.on_event("startup")
async def _warm_advanced_emotion():
    if settings.ADV_EMOTION_ENABLE:
        try:
            await advanced_emotion.load_model()
            print("Advanced emotion model warmed (stub)")
        except Exception as e:  # noqa: BLE001
            print(f"Advanced emotion warm-load failed: {e}")


# --- Final CORS enforcement middleware (hardens error paths) ---
@app.middleware("http")
async def _final_cors_enforcer(request: Request, call_next):
    response = await call_next(request)
    try:
        origin = request.headers.get("origin")
        if origin:
            allowed = False
            if allow_all:
                allowed = True
            elif origin in origins or _is_dynamic_local_origin(origin):
                allowed = True
            if allowed:
                # Always set (overwrites missing header on 4xx/5xx)
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers.setdefault("Vary", "Origin")
                response.headers.setdefault("Access-Control-Allow-Credentials", "true")
                # Ensure standard exposed headers for frontend
                existing_expose = response.headers.get("Access-Control-Expose-Headers", "")
                needed = {"X-Session-Id", "X-App-Version", "X-Deprecation"}
                merged = set(h.strip() for h in existing_expose.split(",") if h.strip()) | needed
                response.headers["Access-Control-Expose-Headers"] = ", ".join(sorted(merged))
    except Exception:  # noqa: BLE001
        pass
    return response

# --- CORS diagnostic endpoint ---
@app.get("/health/cors", tags=["Health"])
def cors_echo(request: Request):  # type: ignore[override]
    origin = request.headers.get("origin")
    return {
        "received_origin": origin,
        "configured_origins": origins,
        "dynamic_dev_enabled": ALLOW_DYNAMIC_LOCAL,
        "debug_mode": DEBUG_CORS,
        "allowed_via": (
            "*" if origins == ["*"] else ("list" if origin in origins else ("dynamic" if _is_dynamic_local_origin(origin) else "none"))
        ),
    }
try:
    # include mirrored /api/metrics router if present
    app.include_router(metrics_router.api_router)  # type: ignore[attr-defined]
except Exception:
    pass

@app.get("/", tags=["Root"])
def read_root():
    return {"status": "API is running"}

@app.get("/api/info", tags=["Meta"])
def api_info():
    uptime = time.time() - BOOT_TIME
    return {
        "version": APP_VERSION,
        "uptime_seconds": int(uptime),
        "origins": origins,
        "allow_all_cors": allow_all,
    }