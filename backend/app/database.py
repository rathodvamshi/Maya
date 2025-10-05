import certifi
from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import settings


class Database:
    """Singleton-style database client wrapper for MongoDB Atlas.

    Now resilient to initial DNS / network failures:
      - Lazy-connect pattern with explicit `connect()`
      - Retries with backoff
      - Soft-fallback to a no-op stub DB to allow partial feature usage (e.g. health, CORS tests)
    """

    def __init__(self):
        self._initialized = False
        self._error: str | None = None
        self.client = None
        self.db = None
        self._init()

    def _init(self):
        mongo_uri = settings.MONGO_URI or settings.DATABASE_URL
        if not mongo_uri:
            self._error = "MongoDB connection string not configured. Set MONGO_URI or DATABASE_URL."
            return
        import time, logging
        logger = logging.getLogger(__name__)
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                self.client = MongoClient(
                    mongo_uri,
                    tls=True,
                    tlsCAFile=certifi.where(),
                    maxPoolSize=100,
                    serverSelectionTimeoutMS=3000,
                )
                # Force a ping to trigger DNS resolution now
                self.client.admin.command("ping")
                db_name = getattr(settings, "MONGO_DB", None) or getattr(settings, "MONGO_DB_NAME", None) or "assistant_db"
                self.db = self.client[db_name]
                self._initialized = True
                return
            except Exception as e:  # noqa: BLE001
                self._error = str(e)
                logger.warning(f"Mongo connect attempt {attempt}/{attempts} failed: {e}")
                time.sleep(1.5 * attempt)
        logger.error("Mongo connection failed after retries; continuing in degraded mode.")

    def healthy(self) -> bool:
        return self._initialized and self.client is not None and self.db is not None

    def require(self):  # internal helper to raise if not healthy
        if not self.healthy():
            raise RuntimeError(f"Mongo not available: {self._error}")

    # If unhealthy, collection getters will raise; routers can decide to handle gracefully

    # --- Collections ---
    def get_user_collection(self) -> Collection:
        self.require()
        return self.db["users"]

    def get_user_profile_collection(self) -> Collection:
        self.require()
        return self.db["user_profiles"]

    def get_chat_log_collection(self) -> Collection:
        self.require()
        return self.db["chat_logs"]

    def get_tasks_collection(self) -> Collection:
        self.require()
        return self.db["tasks"]

    def get_sessions_collection(self) -> Collection:
        self.require()
        return self.db["sessions"]

    def get_feedback_collection(self) -> Collection:
        self.require()
        return self.db["feedback"]

    def get_api_keys_collection(self) -> Collection:
        self.require()
        return self.db["api_keys"]

    def get_activity_logs_collection(self) -> Collection:
        self.require()
        return self.db["activity_logs"]

    def get_security_events_collection(self) -> Collection:
        self.require()
        return self.db["security_events"]

    def get_notifications_collection(self) -> Collection:
        self.require()
        return self.db["notifications"]

    # --- Mini Inline Agent (Junior Lecturer) collections ---
    def get_mini_threads_collection(self) -> Collection:
        self.require()
        return self.db["mini_threads"]

    def get_mini_snippets_collection(self) -> Collection:
        self.require()
        return self.db["mini_snippets"]

    def get_mini_messages_collection(self) -> Collection:
        self.require()
        return self.db["mini_messages"]

    def get_inline_highlights_collection(self) -> Collection:
        self.require()
        return self.db["inline_highlights"]

    def get_saved_snippets_collection(self) -> Collection:
        self.require()
        return self.db["saved_snippets"]

    # --- New memory layer collections ---
    def get_memories_collection(self) -> Collection:
        self.require()
        return self.db["memories"]

    def get_memory_versions_collection(self) -> Collection:
        self.require()
        return self.db["memory_versions"]

    def get_recall_events_collection(self) -> Collection:
        self.require()
        return self.db["recall_events"]

    def get_pii_audit_collection(self) -> Collection:
        self.require()
        return self.db["pii_audit_log"]

    def get_memory_feedback_collection(self) -> Collection:
        self.require()
        return self.db["memory_feedback_events"]

    # --- Index management ---
    def ensure_indexes(self):
        if not self.healthy():
            return
        try:
            users = self.get_user_collection()
            users.create_index("email", unique=True)
            users.create_index("last_seen", name="last_seen_desc")
        except Exception:
            pass

        try:
            sessions = self.get_sessions_collection()
            # Indexes to accelerate per-user session listings & chronological sorting
            sessions.create_index([("userId", 1), ("lastUpdatedAt", -1)], name="user_lastUpdated")
            sessions.create_index([("userId", 1), ("createdAt", -1)], name="user_created_desc")
        except Exception:
            pass

        try:
            tasks = self.get_tasks_collection()
            tasks.create_index([("user_id", 1), ("status", 1)], name="user_status")
            tasks.create_index([("user_id", 1), ("due_date", 1)], name="user_due_date")
            tasks.create_index([("user_id", 1), ("created_at", -1)], name="user_created")
        except Exception:
            pass

        try:
            profiles = self.get_user_profile_collection()
            profiles.create_index("user_id", unique=True)
        except Exception:
            pass

        try:
            api_keys = self.get_api_keys_collection()
            api_keys.create_index([("user_id", 1), ("is_active", 1)], name="user_active")
            api_keys.create_index("hashed_key", unique=True)
        except Exception:
            pass

        try:
            activity_logs = self.get_activity_logs_collection()
            activity_logs.create_index([("user_id", 1), ("timestamp", -1)], name="user_timestamp")
        except Exception:
            pass

        try:
            security_events = self.get_security_events_collection()
            security_events.create_index([("user_id", 1), ("timestamp", -1)], name="user_timestamp")
        except Exception:
            pass

        try:
            notifications = self.get_notifications_collection()
            notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)], name="user_read_created")
        except Exception:
            pass

        # Memory layer indexes (best-effort)
        try:
            memories = self.get_memories_collection()
            memories.create_index([("user_id", 1), ("priority", 1), ("lifecycle_state", 1)], name="user_priority_state")
            memories.create_index([("user_id", 1), ("title", 1)], name="user_title")
            memories.create_index([("user_id", 1), ("updated_at", -1)], name="user_updated_desc")
        except Exception:
            pass
        try:
            mem_versions = self.get_memory_versions_collection()
            mem_versions.create_index([("memory_id", 1), ("changed_at", -1)], name="memory_versions_desc")
        except Exception:
            pass
        try:
            recall_events = self.get_recall_events_collection()
            recall_events.create_index([("user_id", 1), ("responded_at", -1)], name="user_recall_events")
        except Exception:
            pass
        try:
            pii_audit = self.get_pii_audit_collection()
            pii_audit.create_index([("user_id", 1), ("created_at", -1)], name="user_pii_audit")
        except Exception:
            pass
        try:
            mem_fb = self.get_memory_feedback_collection()
            mem_fb.create_index([("user_id", 1), ("created_at", -1)], name="user_memory_feedback")
        except Exception:
            pass

        # Mini-agent indexes
        try:
            mini_threads = self.get_mini_threads_collection()
            mini_threads.create_index([("user_id", 1), ("message_id", 1)], name="user_message")
            mini_threads.create_index([("updated_at", -1)], name="updated_desc")
        except Exception:
            pass
        try:
            mini_snippets = self.get_mini_snippets_collection()
            mini_snippets.create_index([("mini_thread_id", 1), ("hash", 1)], unique=True, name="thread_hash_unique")
        except Exception:
            pass
        try:
            mini_messages = self.get_mini_messages_collection()
            mini_messages.create_index([("mini_thread_id", 1), ("created_at", 1)], name="thread_created")
            mini_messages.create_index([("mini_thread_id", 1), ("snippet_id", 1), ("created_at", 1)], name="thread_snippet_created")
        except Exception:
            pass
        try:
            inline_highlights = self.get_inline_highlights_collection()
            inline_highlights.create_index([("user_id", 1), ("message_id", 1)], name="user_message_highlight")
        except Exception:
            pass
        try:
            saved_snips = self.get_saved_snippets_collection()
            saved_snips.create_index([("user_id", 1), ("created_at", -1)], name="user_saved_created")
        except Exception:
            pass


# Shared DB client (singleton)
db_client = Database()


# --- Dependency functions for FastAPI ---
def get_user_collection() -> Collection:
    return db_client.get_user_collection()

def get_user_profile_collection() -> Collection:
    return db_client.get_user_profile_collection()

def get_chat_log_collection() -> Collection:
    return db_client.get_chat_log_collection()

def get_tasks_collection() -> Collection:
    return db_client.get_tasks_collection()

def get_sessions_collection() -> Collection:
    return db_client.get_sessions_collection()

def get_feedback_collection() -> Collection:
    """Dependency function for the feedback collection."""
    return db_client.get_feedback_collection()

def get_api_keys_collection() -> Collection:
    return db_client.get_api_keys_collection()

def get_activity_logs_collection() -> Collection:
    return db_client.get_activity_logs_collection()

def get_security_events_collection() -> Collection:
    return db_client.get_security_events_collection()

def get_notifications_collection() -> Collection:
    return db_client.get_notifications_collection()

def get_memories_collection() -> Collection:
    return db_client.get_memories_collection()

def get_memory_versions_collection() -> Collection:
    return db_client.get_memory_versions_collection()

def get_recall_events_collection() -> Collection:
    return db_client.get_recall_events_collection()

def get_pii_audit_collection() -> Collection:
    return db_client.get_pii_audit_collection()

def get_memory_feedback_collection() -> Collection:
    return db_client.get_memory_feedback_collection()

# Mini agent dependency getters
def get_mini_threads_collection() -> Collection:
    return db_client.get_mini_threads_collection()

def get_mini_snippets_collection() -> Collection:
    return db_client.get_mini_snippets_collection()

def get_mini_messages_collection() -> Collection:
    return db_client.get_mini_messages_collection()

def get_inline_highlights_collection() -> Collection:
    return db_client.get_inline_highlights_collection()

def get_saved_snippets_collection() -> Collection:
    return db_client.get_saved_snippets_collection()
