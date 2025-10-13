# backend/app/config.py
# ==================================================
# Configuration management for Project Maya Backend
# ==================================================

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os


class Settings(BaseSettings):
    """
    Centralized configuration for all backend services.
    Reads values from environment variables or a `.env` file.
    """

    # ==================================================
    # Database & Security
    # ==================================================
    MONGO_URI: str | None = None                 # MongoDB connection string
    MONGO_DB: str = "MAYA"                       # MongoDB database name
    DATABASE_URL: str | None = None              # Optional fallback DB URL

    SECRET_KEY: str                              # JWT signing key
    ALGORITHM: str                               # JWT algorithm (e.g., HS256)
    ACCESS_TOKEN_EXPIRE_MINUTES: int             # JWT access token expiry (minutes)
    REFRESH_TOKEN_EXPIRE_DAYS: int               # JWT refresh token expiry (days)

    # ==================================================
    # AI / Embeddings / Vector DB
    # ==================================================
    PINECONE_API_KEY: str                        # Pinecone API key
    PINECONE_ENVIRONMENT: str | None = None      # Pinecone region (e.g., us-east-1)
    PINECONE_ENV: str | None = None              # Backward compatible alias
    PINECONE_INDEX: str = "maya2-session-memory" # Default Pinecone index name

    GEMINI_API_KEYS: str                         # Google Gemini API key(s)
    COHERE_API_KEY: str                          # Cohere API key
    ANTHROPIC_API_KEY: str                       # Anthropic Claude API key

    AI_PROVIDER_FAILURE_TIMEOUT: int = 300       # Retry delay for failed AI provider
    AI_PRIMARY_TIMEOUT: float = 2.2              # Primary AI request timeout (seconds)
    AI_FALLBACK_TIMEOUT: float = 4.5             # Fallback AI request timeout (seconds)
    AI_ENABLE_HEDGED: bool = True                # Parallel hedged requests
    AI_HEDGE_DELAY_MS: int = 90                  # Delay between hedge requests
    AI_MAX_PARALLEL: int = 2                     # Max parallel AI requests
    AI_PROVIDER_ORDER: str | None = None         # Comma-separated override order

    EMBEDDING_MODEL_VERSION: str = "gemini-text-embedding-004-v1"

    # ==================================================
    # Redis (Caching / Sessions)
    # ==================================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # ==================================================
    # Neo4j Knowledge Graph
    # ==================================================
    NEO4J_URI: str                               # Example: bolt://localhost:7688
    NEO4J_CONTAINER_URI: str | None = None       # Optional container override
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    # ==================================================
    # Email / Notifications (SMTP)
    # ==================================================
    MAIL_USERNAME: str                           # Gmail address
    MAIL_PASSWORD: str                           # Gmail app password
    MAIL_FROM: str                               # Sender email
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    SMTP_USER: str | None = None                 # Backward compatibility
    SMTP_PASS: str | None = None                 # Backward compatibility

    # ==================================================
    # API Limits / Quotas
    # ==================================================
    API_MONTHLY_LIMIT: int = 20

    # ==================================================
    # Feature Toggles / Personalization
    # ==================================================
    ENABLE_PERSONA_RESPONSE: bool = True
    PERSONA_STYLE: str = "best_friend"
    PERSONA_MEMORY_TURNS: int = 15

    ENABLE_SUGGESTIONS: bool = True
    SUGGESTION_HISTORY_WINDOW: int = 30

    ENABLE_EMOTION_PERSONA: bool = True
    ENABLE_EMOJI_ENRICHMENT: bool = True
    EMOJI_MAX_AUTO_ADD: int = 3
    EMOJI_MAX_TOTAL: int = 6

    # ==================================================
    # External APIs
    # ==================================================
    YOUTUBE_API_KEY: str | None = None
    NEWS_API_KEY: str | None = None
    WEATHER_API_KEY: str | None = None

    # ==================================================
    # Pydantic Configuration
    # ==================================================
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_prefix="",
        extra="ignore"
    )

    # ==================================================
    # Post Initialization Adjustments
    # ==================================================
    def model_post_init(self, __context) -> None:
        """Normalize and auto-fill environment variables."""
        try:
            # Normalize Pinecone env var name
            if not self.PINECONE_ENVIRONMENT and self.PINECONE_ENV:
                object.__setattr__(self, "PINECONE_ENVIRONMENT", self.PINECONE_ENV)

            # Auto-fill backward-compatible SMTP variables
            if not self.SMTP_USER and self.MAIL_USERNAME:
                object.__setattr__(self, "SMTP_USER", self.MAIL_USERNAME)
            if not self.SMTP_PASS and self.MAIL_PASSWORD:
                object.__setattr__(self, "SMTP_PASS", self.MAIL_PASSWORD)

            # Docker environment adjustments
            if os.path.exists("/.dockerenv"):
                if self.NEO4J_CONTAINER_URI:
                    object.__setattr__(self, "NEO4J_URI", self.NEO4J_CONTAINER_URI)
                elif "localhost" in self.NEO4J_URI:
                    object.__setattr__(self, "NEO4J_URI", self.NEO4J_URI.replace("localhost", "neo4j"))

                if self.REDIS_HOST in ("localhost", "127.0.0.1"):
                    object.__setattr__(self, "REDIS_HOST", "redis")

        except Exception:
            pass


# ==================================================
# Global Settings Instance
# ==================================================
settings = Settings()
