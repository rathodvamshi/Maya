import certifi
from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import settings


class Database:
    """Singleton-style database client wrapper for MongoDB Atlas."""

    def __init__(self):
        # Prefer MONGO_URI from settings; fallback to DATABASE_URL for backward compatibility
        mongo_uri = settings.MONGO_URI or settings.DATABASE_URL
        if not mongo_uri:
            raise RuntimeError("MongoDB connection string not configured. Set MONGO_URI or DATABASE_URL.")

        # Connect to MongoDB Atlas (TLS required) with pooling settings per blueprint
        # Note: serverSelectionTimeoutMS keeps failover snappy
        self.client = MongoClient(
            mongo_uri,
            tls=True,
            tlsCAFile=certifi.where(),
            maxPoolSize=100,
            serverSelectionTimeoutMS=3000,
        )

        db_name = getattr(settings, "MONGO_DB", None) or getattr(settings, "MONGO_DB_NAME", None) or "assistant_db"
        self.db = self.client[db_name]

    # --- Collections ---
    def get_user_collection(self) -> Collection:
        return self.db["users"]

    def get_user_profile_collection(self) -> Collection:
        return self.db["user_profiles"]

    def get_chat_log_collection(self) -> Collection:
        return self.db["chat_logs"]

    def get_tasks_collection(self) -> Collection:
        return self.db["tasks"]

    def get_sessions_collection(self) -> Collection:
        return self.db["sessions"]

    def get_feedback_collection(self) -> Collection:
        """Returns a reference to the 'feedback' collection."""
        return self.db["feedback"]

    # --- Index management ---
    def ensure_indexes(self):
        try:
            users = self.get_user_collection()
            users.create_index("email", unique=True)
            users.create_index("last_seen", name="last_seen_desc")
        except Exception:
            pass

        try:
            sessions = self.get_sessions_collection()
            sessions.create_index([("userId", 1), ("lastUpdatedAt", -1)], name="user_lastUpdated")
        except Exception:
            pass

        try:
            tasks = self.get_tasks_collection()
            tasks.create_index([("email", 1), ("status", 1)], name="email_status")
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
