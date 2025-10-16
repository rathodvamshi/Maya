import time
import logging
from app.config import settings
# ✅ Gemini-only provider
from app.services import gemini_service

logger = logging.getLogger(__name__)

# --- Global state ---
FAILED_PROVIDERS: dict[str, float] = {}

# ✅ Providers in priority order (Gemini ONLY)
EMBEDDING_PROVIDERS = [
    ("gemini", gemini_service.create_embedding),
]

def is_provider_available(name: str) -> bool:
    """Check if a provider is available (i.e., not in failure timeout)."""
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[Embedding] Provider '{name}' is in cooldown, skipping.")
        return False
    return True


def create_embedding(text: str) -> list[float] | None:
    """
    Creates an embedding sized to settings.PINECONE_DIMENSIONS using the primary provider (Gemini).
    Falls back to other providers if configured.
    """
    required_dim = getattr(settings, "PINECONE_DIMENSIONS", 1024)
    for name, provider_func in EMBEDDING_PROVIDERS:
        if not is_provider_available(name):
            continue
        try:
            logger.info(f"[Embedding] Trying provider '{name}'.")
            embedding = provider_func(text)
            if not embedding or len(embedding) != required_dim:
                raise ValueError(
                    f"Invalid embedding received from {name}. Dimension: {len(embedding) if embedding else 'None'} (expected {required_dim})"
                )
            FAILED_PROVIDERS.pop(name, None)
            return embedding
        except Exception as e:
            logger.error(f"[Embedding] Provider '{name}' failed: {e}")
            FAILED_PROVIDERS[name] = time.time()

    logger.critical("🚨 All compatible embedding providers failed.")
    return None
