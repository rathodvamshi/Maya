"""Gemini service: text generation and 1536-d embeddings with key rotation and retries."""

import time
import logging
from typing import List
import httpx
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

# --- Global State for Key Rotation ---
gemini_keys = [key.strip() for key in (settings.GEMINI_API_KEYS or "").split(',') if key.strip()]
current_gemini_key_index = 0

def _configure_genai_with_current_key():
    key_to_try = gemini_keys[current_gemini_key_index]
    genai.configure(api_key=key_to_try)


def generate(prompt: str) -> str:
    """Attempts to get a response from Gemini, rotating keys on failure."""
    global current_gemini_key_index
    if not gemini_keys:
        raise ConnectionError("Gemini API keys are not configured.")

    start_index = current_gemini_key_index
    while True:
        try:
            _configure_genai_with_current_key()
            model_name = getattr(settings, "GOOGLE_MODEL", None) or "gemini-2.5-flash"
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.warning(f"⚠️ Gemini key at index {current_gemini_key_index} failed for generate: {e}")
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)
            if current_gemini_key_index == start_index:
                raise RuntimeError(f"All Gemini API keys failed. Last error: {e}")


def _adapt_dimension(vec: List[float] | None, required_dim: int) -> List[float]:
    """Adapt an embedding vector to the required dimension.

    - If vec is None, returns an empty list to indicate failure upstream.
    - If shorter than required, zero-pad to match length (preserves cosine similarity among Gemini vectors).
    - If longer than required, truncate to required length.
    """
    if not vec:
        return []
    n = len(vec)
    if n == required_dim:
        return vec
    if n < required_dim:
        # Zero-pad tail to reach required dimension
        return vec + [0.0] * (required_dim - n)
    # Truncate
    return vec[:required_dim]


def create_embedding(text: str, *, retries: int = 3, backoff: float = 0.8) -> List[float]:
    """Create an embedding using Gemini and adapt to configured dimension.

    We request the configured output dimensionality, but if the API returns a
    fixed size (commonly 768 for text-embedding-004), we adapt by zero-padding
    or truncation to match settings.PINECONE_DIMENSIONS.
    """
    global current_gemini_key_index
    if not gemini_keys:
        raise ConnectionError("Gemini API keys are not configured.")

    start_index = current_gemini_key_index
    attempt = 0
    last_err: Exception | None = None
    required_dim = getattr(settings, "PINECONE_DIMENSIONS", 1536)
    while attempt < max(1, retries):
        try:
            _configure_genai_with_current_key()
            # google-generativeai v0.7+ supports dict with additionalConfig for embeddings
            # Use the v1 models path alias 'models/text-embedding-004' which supports output_dimensionality
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
                # The library supports passing as keyword: output_dimensionality (may be ignored on some versions)
                output_dimensionality=required_dim,
            )
            vec = result.get("embedding") if isinstance(result, dict) else getattr(result, "embedding", None)
            # google-generativeai sometimes returns a bare list; sometimes {'embedding': [...]}
            if isinstance(vec, dict):
                # library shape can vary; normalize to values
                v = vec.get("values") or vec.get("embedding")
                if v:
                    vec = v
            if vec:
                adapted = _adapt_dimension(vec, required_dim)
                if adapted:
                    if len(adapted) != required_dim:
                        raise ValueError(f"Adapted embedding has wrong dimension {len(adapted)}")
                    return adapted  # type: ignore

            # Fallback to REST API with explicit outputDimensionality if library ignores it
            key = gemini_keys[current_gemini_key_index]
            # Prefer v1beta endpoint which reliably honors outputDimensionality
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={key}"
            payload = {
                "model": "models/text-embedding-004",
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_DOCUMENT",
                "outputDimensionality": required_dim,
            }
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                emb = None
                # Response may be {"embedding": {"values": [...]}}
                if isinstance(data, dict):
                    emb_obj = data.get("embedding")
                    if isinstance(emb_obj, dict):
                        emb = emb_obj.get("values") or emb_obj.get("embedding")
                    elif isinstance(emb_obj, list):
                        emb = emb_obj
                adapted = _adapt_dimension(emb, required_dim)
                if not adapted:
                    raise ValueError("Gemini REST returned empty embedding")
                if len(adapted) != required_dim:
                    raise ValueError(f"Adapted REST embedding has wrong dimension {len(adapted)}")
                return adapted
        except Exception as e:
            last_err = e
            logger.warning(f"⚠️ Gemini embedding attempt failed (attempt={attempt+1}): {e}")
            # Rotate key and exponential backoff
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)
            if attempt < retries - 1:
                sleep_s = min(2.5, backoff * (1.8 ** attempt))
                time.sleep(sleep_s)
            attempt += 1
            if current_gemini_key_index == start_index and attempt >= retries:
                break
    raise RuntimeError(f"All Gemini API keys failed for embeddings. Last error: {last_err}")