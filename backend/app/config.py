# backend/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os


class Settings(BaseSettings):
    """
    Centralized application configuration.
    All values are read from environment variables or a `.env` file.
    """

    # ==================================================
    # 🔹 Database & Security
    # ==================================================
    # Prefer Mongo-style names per blueprint; keep DATABASE_URL for backward compatibility
    MONGO_URI: str | None = None         # Mongo Atlas SRV connection (mongodb+srv://...)
    MONGO_DB: str = "assistant_db"       # Database name (default preserved)
    DATABASE_URL: str | None = None      # Back-compat: will be used if MONGO_URI is not provided
    SECRET_KEY: str                      # JWT signing key
    ALGORITHM: str                       # JWT algorithm (e.g., HS256)
    ACCESS_TOKEN_EXPIRE_MINUTES: int     # Expiry for access tokens (minutes)
    REFRESH_TOKEN_EXPIRE_DAYS: int       # Expiry for refresh tokens (days)

    # ==================================================
    # 🔹 AI / Embeddings / Vector DB
    # ==================================================
    PINECONE_API_KEY: str                # Pinecone API key
    # Support both PINECONE_ENV (blueprint) and PINECONE_ENVIRONMENT (legacy)
    PINECONE_ENVIRONMENT: str | None = None
    PINECONE_ENV: str | None = None
    PINECONE_INDEX: str = "maya2-session-memory"   # Default index name used in services

    # AI provider API keys (all REQUIRED for now)
    GEMINI_API_KEYS: str                 # Google Gemini (comma-separated keys)
    COHERE_API_KEY: str                  # Cohere API key
    ANTHROPIC_API_KEY: str               # Anthropic Claude API key
    # Optional direct LLM endpoints (if using HTTP providers proxied through a gateway)
    LLM_PRIMARY_URL: str | None = None
    LLM_FALLBACK_URL: str | None = None

    # If one provider fails, wait N seconds before retrying
    AI_PROVIDER_FAILURE_TIMEOUT: int = 300  
    AI_PROVIDER_ORDER: str | None = None      # Comma-separated override order e.g. "gemini,cohere,anthropic"
    AI_PRIMARY_TIMEOUT: float = 3.0           # Seconds allowed for first provider attempt
    AI_FALLBACK_TIMEOUT: float = 6.0          # Seconds allowed for each fallback provider
    # Hedged parallel invocation config (for latency racing across providers)
    AI_ENABLE_HEDGED: bool = False            # Enable hedged parallel provider racing
    AI_HEDGE_DELAY_MS: int = 160              # Delay before launching hedge (ms) or dynamic threshold whichever earlier
    AI_MAX_PARALLEL: int = 3                  # Max providers to race in parallel (includes primary)

    # ==================================================
    # 🔹 Embedding Model Versioning
    # ==================================================
    EMBEDDING_MODEL_VERSION: str = "gemini-text-embedding-004-v1"  # Bump to trigger re-embedding pipeline

    # ==================================================
    # 🔹 Proactive Recall Gating Thresholds
    # ==================================================
    MEMORY_GATE_MIN_SALIENCE: float = 0.85          # Below this salience -> gated
    MEMORY_GATE_MIN_TRUST: float = 0.55             # Below this trust.confidence -> gated
    MEMORY_GATE_MIN_COMPOSITE: float = 0.35         # Optional: similarity * salience * trust must exceed
    MEMORY_GATE_ENABLE: bool = True                 # Master toggle
    MEMORY_GATE_LOG_SKIPPED: bool = True            # When enabled, skipped low-quality memories appear in recall event (flagged gated)

    # ==================================================
    # 🔹 Distillation Scan Limits
    # ==================================================
    DISTILLATION_SCAN_GLOBAL_CAP: int = 25          # Max distilled summaries created per scan run (global)
    DISTILLATION_SCAN_PER_USER_CAP: int = 2         # Max summaries per user per scan
    DISTILLATION_GROUP_SIZE: int = 8                # Max originals grouped into one distilled summary

    # ==================================================
    # 🔹 Redis (optional, for caching / sessions)
    # ==================================================
    REDIS_HOST: str = "localhost"        # Redis host (default: local)
    REDIS_PORT: int = 6379               # Redis port
    REDIS_DB: int = 0                    # Redis DB index
    REDIS_PASSWORD: str | None = None    # Redis password (if set)

    # ==================================================
    # 🔹 Neo4j Knowledge Graph
    # ==================================================
    NEO4J_URI: str                       # Example: "bolt://localhost:7687"
    NEO4J_CONTAINER_URI: str | None = None  # Optional explicit container URI (e.g. bolt://neo4j:7687)
    NEO4J_USER: str                      # Neo4j username
    NEO4J_PASSWORD: str                  # Neo4j password

    # ==================================================
    # 🔹 Email Configuration
    # ==================================================
    MAIL_USERNAME: str                   # SMTP username
    MAIL_PASSWORD: str                   # SMTP password / App password
    MAIL_FROM: str                       # Default sender email
    MAIL_SERVER: str = "smtp.gmail.com"  # SMTP server
    MAIL_PORT: int = 587                 # Port (587 = TLS, 465 = SSL)
    MAIL_STARTTLS: bool = True           # Enable STARTTLS
    MAIL_SSL_TLS: bool = False           # Enable SSL/TLS (usually for port 465)

    # ==================================================
    # 🔹 Rate Limits / Quotas
    # ==================================================
    API_MONTHLY_LIMIT: int = 20          # Max requests per month per user

    # ==================================================
    # 🔹 Emotion / Emoji Enrichment (lightweight heuristics + optional advanced module)
    # ==================================================
    ENABLE_EMOTION_PERSONA: bool = True          # Enable adding persona guidance based on detected emotion
    ENABLE_EMOJI_ENRICHMENT: bool = True          # Enable automatic emoji enrichment in AI replies
    EMOJI_MAX_AUTO_ADD: int = 3                   # Max emojis the system may add (in addition to any model output)
    EMOJI_MAX_TOTAL: int = 6                      # Hard cap on total emojis after enrichment
    EMOTION_TREND_WINDOW: int = 12                # Number of recent emotions to inspect for escalation streaks
    EMOTION_ESCALATION_THRESHOLD: int = 3         # Repeated occurrences that trigger escalation guidance
    ADV_EMOTION_ENABLE: bool = False              # Toggle for advanced model-based emotion detection (future)
    ADV_EMOTION_CONFIDENCE_THRESHOLD: float = 0.45  # Confidence threshold for advanced model emoji suggestion
    ADV_EMOTION_ENTROPY_THRESHOLD: float = 1.85     # Entropy gating for advanced model
    EMOJI_MAP_PATH: str = "backend/config/emotion_to_emoji.yml"  # Path to YAML mapping (override with env)

    # ==================================================
    # 🔹 Persona Friend Layer
    # ==================================================
    ENABLE_PERSONA_RESPONSE: bool = True        # Master toggle for persona best-friend layer
    PERSONA_STYLE: str = "best_friend"          # best_friend | neutral | professional (future)
    PERSONA_MEMORY_TURNS: int = 15              # Rolling turns to keep for persona contextual warmth

    # ==================================================
    # 🔹 Config Behavior
    # ==================================================
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        extra="forbid"
    )

    # Adjust a few settings automatically when running inside Docker containers so
    # services resolve by docker-compose service names instead of localhost.
    def model_post_init(self, __context) -> None:  # pydantic v2 hook
        try:
            # Normalize Pinecone env var names
            if not self.PINECONE_ENVIRONMENT and self.PINECONE_ENV:
                object.__setattr__(self, "PINECONE_ENVIRONMENT", self.PINECONE_ENV)

            # Heuristic: Docker creates this file inside containers
            if os.path.exists("/.dockerenv"):
                # Inside container: prefer explicit container URI if provided
                if self.NEO4J_CONTAINER_URI:
                    object.__setattr__(self, "NEO4J_URI", self.NEO4J_CONTAINER_URI)
                else:
                    # Fallback heuristic replacement
                    if isinstance(self.NEO4J_URI, str) and "localhost" in self.NEO4J_URI:
                        object.__setattr__(self, "NEO4J_URI", self.NEO4J_URI.replace("localhost", "neo4j"))
                if self.REDIS_HOST in ("localhost", "127.0.0.1"):
                    object.__setattr__(self, "REDIS_HOST", "redis")
        except Exception:
            # Never fail app boot due to a convenience override
            pass


# ✅ Create a global settings instance
settings = Settings()
