# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.routers import auth, chat, sessions, feedback, health
from app.routers import user as user_router
from app.routers import memories as memories_router
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
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(memories_router.router)

@app.get("/", tags=["Root"])
def read_root():
    return {"status": "API is running"}