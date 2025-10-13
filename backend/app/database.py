# backend/app/database.py
"""
Upgraded MongoDB client wrapper for MongoDB Atlas with:
 - lazy / explicit connect support
 - retry with exponential backoff
 - optional async Motor support if `motor` is installed and settings.MONGO_ASYNC True
 - graceful degraded-mode NoOp collections so the app can run with partial functionality
 - robust index creation with idempotent calls and logging
 - health checks, ping, close
 - Fast dependency getters for FastAPI that return a usable object even in degraded mode

Usage:
 - Import `db_client` from this module. At app startup call `db_client.connect()` (optional).
 - Use dependency functions (get_tasks_collection, ...) in FastAPI route dependencies as before.
"""

from __future__ import annotations

import certifi
import asyncio
import time
import logging
from typing import Optional, Any, Dict
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from bson import ObjectId
from pymongo import MongoClient

from app.config import settings

logger = logging.getLogger(__name__)

# Simple degraded-mode collection that allows reads to return empty results and
# write operations to raise or no-op depending on method. This keeps the app alive
# in cases where DB is temporarily unreachable.
class NoOpCollection:
    def __init__(self, name: str):
        self._name = name

    # Read-like methods return empty/neutral values
    def find_one(self, *args, **kwargs):
        logger.debug("[NoOpCollection] find_one called on %s; returning None", self._name)
        return None

    def find(self, *args, **kwargs):
        logger.debug("[NoOpCollection] find called on %s; returning empty iterator", self._name)
        return iter([])

    def aggregate(self, *args, **kwargs):
        logger.debug("[NoOpCollection] aggregate called on %s; returning empty iterator", self._name)
        return iter([])

    def count_documents(self, *args, **kwargs):
        logger.debug("[NoOpCollection] count_documents called on %s; returning 0", self._name)
        return 0

    def distinct(self, *args, **kwargs):
        logger.debug("[NoOpCollection] distinct called on %s; returning []", self._name)
        return []

    # Write-like operations: log and raise to alert caller, but do not crash the app at import time
    def insert_one(self, *args, **kwargs):
        logger.warning("[NoOpCollection] insert_one called on %s while DB degraded", self._name)
        raise RuntimeError("Database is not available (degraded mode).")

    def insert_many(self, *args, **kwargs):
        logger.warning("[NoOpCollection] insert_many called on %s while DB degraded", self._name)
        raise RuntimeError("Database is not available (degraded mode).")

    def update_one(self, *args, **kwargs):
        logger.warning("[NoOpCollection] update_one called on %s while DB degraded", self._name)
        raise RuntimeError("Database is not available (degraded mode).")

    def update_many(self, *args, **kwargs):
        logger.warning("[NoOpCollection] update_many called on %s while DB degraded", self._name)
        raise RuntimeError("Database is not available (degraded mode).")

    def delete_one(self, *args, **kwargs):
        logger.warning("[NoOpCollection] delete_one called on %s while DB degraded", self._name)
        raise RuntimeError("Database is not available (degraded mode).")

    def delete_many(self, *args, **kwargs):
        logger.warning("[NoOpCollection] delete_many called on %s while DB degraded", self._name)
        raise RuntimeError("Database is not available (degraded mode).")

    def create_index(self, *args, **kwargs):
        logger.debug("[NoOpCollection] create_index called on %s; ignoring in degraded mode", self._name)
        return None

    # Allow attribute access to behave like a real collection in limited ways
    def __getattr__(self, item):
        # For pymongo Collection properties we don't implement, return a stub that raises
        def _stub(*args, **kwargs):
            logger.debug("[NoOpCollection] stub %s called on %s", item, self._name)
            raise RuntimeError("Database is not available (degraded mode).")
        return _stub


class Database:
    """
    Resilient database wrapper.

    Behavior:
     - Tries to connect on initialization (with limited retries) but will not raise at import time.
     - You may call connect() explicitly (recommended) during app startup to ensure availability.
     - If MongoDB is unreachable, collection getters return NoOpCollection instances so the app can continue operating in a degraded mode.
     - ensure_indexes() will attempt to create indexes; failures are logged but non-fatal.
    """

    def __init__(self):
        self._initialized: bool = False
        self._error: Optional[str] = None
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[Any] = None  # actual Database object from motor
        self._mongo_uri: Optional[str] = None
        self._db_name: str = "assistant_db"
        # Discover config
        self._discover_settings()
        # Try to init lazily (non-fatal)
        # Async connect must be called explicitly

    def _discover_settings(self):
        self._mongo_uri = getattr(settings, "MONGO_URI", None) or getattr(settings, "DATABASE_URL", None)
        # Database name resolution: allow several config keys
        self._db_name = getattr(settings, "MONGO_DB", None) or getattr(settings, "MONGO_DB_NAME", None) or getattr(settings, "DATABASE_NAME", None) or "assistant_db"

    async def connect(self, attempts: int = 3, base_delay: float = 1.0) -> bool:
        """
        Async connect call (use during app startup). Returns True if connection established.
        """
        if not self._mongo_uri:
            self._error = "MongoDB connection string not configured. Set MONGO_URI or DATABASE_URL."
            logger.warning(self._error)
            return False

        for attempt in range(1, attempts + 1):
            try:
                self._client = AsyncIOMotorClient(
                    self._mongo_uri,
                    tls=True,
                    tlsCAFile=certifi.where(),
                    maxPoolSize=getattr(settings, "MONGO_MAX_POOL", 100),
                )
                self._db = self._client[self._db_name]
                # Ping the server
                await self._db.command("ping")
                self._initialized = True
                self._error = None
                logger.info("MongoDB (Motor) connected to %s (db=%s)", self._mongo_uri, self._db_name)
                return True
            except Exception as exc:
                self._error = str(exc)
                logger.warning("Motor connect attempt %d/%d failed: %s", attempt, attempts, exc)
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        logger.error("Motor connection failed after %d attempts; running in degraded mode. Last error: %s", attempts, self._error)
        return False

    def connect(self, attempts: int = 5, base_delay: float = 1.0) -> bool:
        """
        Explicit connect call (use during app startup). Returns True if connection established.
        Retries `attempts` times with exponential backoff.
        """
        if self.healthy():
            return True
        self._discover_settings()
        for attempt in range(1, attempts + 1):
            try:
                self._client = MongoClient(
                    self._mongo_uri,
                    tls=True,
                    tlsCAFile=certifi.where(),
                    maxPoolSize=getattr(settings, "MONGO_MAX_POOL", 100),
                    serverSelectionTimeoutMS=int(getattr(settings, "MONGO_SERVER_SELECTION_TIMEOUT_MS", 3000)),
                    socketTimeoutMS=int(getattr(settings, "MONGO_SOCKET_TIMEOUT_MS", 60000)),
                )
                self._client.admin.command("ping")
                self._db = self._client[self._db_name]
                self._initialized = True
                self._error = None
                logger.info("MongoDB connected on explicit call (db=%s).", self._db_name)
                return True
            except Exception as exc:
                self._error = str(exc)
                logger.warning("Explicit Mongo connect %d/%d failed: %s", attempt, attempts, exc)
                time.sleep(base_delay * (2 ** (attempt - 1)))
        logger.error("Explicit Mongo connect failed after %d attempts; running in degraded mode", attempts)
        return False

    def close(self):
        """Close the underlying MongoClient if present."""
        try:
            if self._client:
                self._client.close()
            self._initialized = False
            self._client = None
            self._db = None
            logger.info("MongoDB client closed.")
        except Exception as exc:
            logger.exception("Error closing Mongo client: %s", exc)

    def healthy(self) -> bool:
        """Return True when the client has an active DB connection."""
        return bool(self._initialized and self._client is not None and self._db is not None)

    def require(self):
        """Raise a runtime error if DB is not healthy (for code paths that must fail fast)."""
        if not self.healthy():
            raise RuntimeError(f"Mongo not available: {self._error or 'unknown error'}")

    def ping(self) -> bool:
        """Ping the server if client exists; return False on error."""
        if not self._client:
            return False
        try:
            self._client.admin.command("ping")
            return True
        except Exception as exc:
            logger.warning("Mongo ping failed: %s", exc)
            return False

    def get_database(self):
        """Return the underlying DB object or None (useful for advanced usage)."""
        return self._db

    # --- Collection getters ---
    # If DB unhealthy, return NoOpCollection instead of raising; this enables degraded mode.
    def _get_collection_or_noop(self, name: str) -> Collection | NoOpCollection:
        if not self.healthy():
            logger.debug("Returning NoOpCollection for %s (DB degraded).", name)
            return NoOpCollection(name)
        try:
            return self._db[name]
        except Exception as exc:
            logger.exception("Failed to get collection %s: %s", name, exc)
            return NoOpCollection(name)

    def get_user_collection(self) -> AsyncIOMotorCollection | NoOpCollection:
        return self._get_collection_or_noop("users")

    def get_user_profile_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("user_profiles")

    def get_chat_log_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("chat_logs")

    def get_tasks_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("tasks")

    def get_sessions_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("sessions")

    def get_feedback_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("feedback")

    def get_api_keys_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("api_keys")

    def get_activity_logs_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("activity_logs")

    def get_security_events_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("security_events")

    def get_notifications_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("notifications")

    def get_email_otps_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("email_otps")

    # Mini-agent collections
    def get_mini_threads_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("mini_threads")

    def get_mini_snippets_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("mini_snippets")

    def get_mini_messages_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("mini_messages")

    def get_inline_highlights_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("inline_highlights")

    def get_saved_snippets_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("saved_snippets")

    # Memory layer
    def get_memories_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("memories")

    def get_memory_versions_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("memory_versions")

    def get_recall_events_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("recall_events")

    def get_pii_audit_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("pii_audit_log")

    def get_memory_feedback_collection(self) -> Collection | NoOpCollection:
        return self._get_collection_or_noop("memory_feedback_events")

    # --- Index management (idempotent & best-effort) ---
    def ensure_indexes(self):
        """
        Create commonly used indexes. Best-effort: failures are logged but do not raise.
        Call this at application startup (once).
        """
        if not self.healthy():
            logger.warning("ensure_indexes skipped: DB not healthy.")
            return

        try:
            users = self.get_user_collection()
            users.create_index("email", unique=True, background=True)
            users.create_index("last_seen", name="last_seen_desc", background=True)
        except Exception:
            logger.exception("Error creating indexes for users collection")

        try:
            sessions = self.get_sessions_collection()
            sessions.create_index([("userId", 1), ("lastUpdatedAt", -1)], name="user_lastUpdated", background=True)
            sessions.create_index([("userId", 1), ("createdAt", -1)], name="user_created_desc", background=True)
        except Exception:
            logger.exception("Error creating indexes for sessions collection")

        try:
            tasks = self.get_tasks_collection()
            tasks.create_index([("user_id", 1), ("status", 1)], name="user_status", background=True)
            tasks.create_index([("user_id", 1), ("due_date", 1)], name="user_due_date", background=True)
            tasks.create_index([("user_id", 1), ("created_at", -1)], name="user_created", background=True)
            # Text index for searching title & description; safe to call repeatedly
            try:
                tasks.create_index([("title", "text"), ("description", "text")], name="task_text_idx", default_language="english", background=True)
            except Exception:
                # If text index exists under different name, ignore
                logger.debug("task_text_idx may already exist or failed to create")
        except Exception:
            logger.exception("Error creating indexes for tasks collection")

        try:
            profiles = self.get_user_profile_collection()
            profiles.create_index("user_id", unique=True, background=True)
        except Exception:
            logger.exception("Error creating indexes for profiles collection")

        try:
            api_keys = self.get_api_keys_collection()
            api_keys.create_index([("user_id", 1), ("is_active", 1)], name="user_active", background=True)
            api_keys.create_index("hashed_key", unique=True, background=True)
        except Exception:
            logger.exception("Error creating indexes for api_keys collection")

        try:
            notifications = self.get_notifications_collection()
            notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)], name="user_read_created", background=True)
        except Exception:
            logger.exception("Error creating indexes for notifications collection")

        # Memory-layer indexes (best-effort)
        try:
            memories = self.get_memories_collection()
            memories.create_index([("user_id", 1), ("priority", 1), ("lifecycle_state", 1)], name="user_priority_state", background=True)
            memories.create_index([("user_id", 1), ("title", 1)], name="user_title", background=True)
            memories.create_index([("user_id", 1), ("updated_at", -1)], name="user_updated_desc", background=True)
        except Exception:
            logger.exception("Error creating indexes for memories collection")

        logger.info("Index creation attempts finished (best-effort).")

# Module-level singleton
db_client = Database()

# FastAPI dependency helper functions (return Collection or NoOpCollection)
def get_user_collection() -> Collection | NoOpCollection:
    return db_client.get_user_collection()

def get_user_profile_collection() -> Collection | NoOpCollection:
    return db_client.get_user_profile_collection()

def get_chat_log_collection() -> Collection | NoOpCollection:
    return db_client.get_chat_log_collection()

def get_tasks_collection() -> Collection | NoOpCollection:
    return db_client.get_tasks_collection()

def get_sessions_collection() -> Collection | NoOpCollection:
    return db_client.get_sessions_collection()

def get_feedback_collection() -> Collection | NoOpCollection:
    return db_client.get_feedback_collection()

def get_api_keys_collection() -> Collection | NoOpCollection:
    return db_client.get_api_keys_collection()

def get_activity_logs_collection() -> Collection | NoOpCollection:
    return db_client.get_activity_logs_collection()

def get_security_events_collection() -> Collection | NoOpCollection:
    return db_client.get_security_events_collection()

def get_notifications_collection() -> Collection | NoOpCollection:
    return db_client.get_notifications_collection()

def get_memories_collection() -> Collection | NoOpCollection:
    return db_client.get_memories_collection()

def get_memory_versions_collection() -> Collection | NoOpCollection:
    return db_client.get_memory_versions_collection()

def get_recall_events_collection() -> Collection | NoOpCollection:
    return db_client.get_recall_events_collection()

def get_pii_audit_collection() -> Collection | NoOpCollection:
    return db_client.get_pii_audit_collection()

def get_memory_feedback_collection() -> Collection | NoOpCollection:
    return db_client.get_memory_feedback_collection()

def get_email_otps_collection() -> Collection | NoOpCollection:
    return db_client.get_email_otps_collection()

def get_mini_threads_collection() -> Collection | NoOpCollection:
    return db_client.get_mini_threads_collection()

def get_mini_snippets_collection() -> Collection | NoOpCollection:
    return db_client.get_mini_snippets_collection()

def get_mini_messages_collection() -> Collection | NoOpCollection:
    return db_client.get_mini_messages_collection()

def get_inline_highlights_collection() -> Collection | NoOpCollection:
    return db_client.get_inline_highlights_collection()

def get_saved_snippets_collection() -> Collection | NoOpCollection:
    return db_client.get_saved_snippets_collection()
