# backend/app/services/cohere_service.py

import cohere
from app.config import settings
from typing import Iterable

# ======================================================
# 🔹 Initialize Cohere Client
# ======================================================
try:
    co = cohere.Client(settings.COHERE_API_KEY)
except Exception as e:
    print(f"[ERROR] Failed to configure Cohere client: {e}")
    co = None  # Fallback to None if config is broken


# ======================================================
# 🔹 Text Generation
# ======================================================
def generate(prompt: str, model: str | None = None) -> str:
    """Generate a conversational response using Cohere's chat API with graceful model fallback.

    Resolution order:
      1. Explicit model param if provided
      2. settings.COHERE_MODEL
      3. Internal fallback list (kept in sync with Cohere public docs)

    If the current model has been sunset (404 w/ removal message) we try the next one.
    """
    if not co:
        raise ConnectionError("Cohere service is not configured.")

    preferred = []
    if model:
        preferred.append(model)
    if settings.COHERE_MODEL and settings.COHERE_MODEL not in preferred:
        preferred.append(settings.COHERE_MODEL)

    # Cohere current (Oct 2025) publicly available Command family examples.
    fallback_sequence: Iterable[str] = (
        "command-r7b",
        "command-r-plus",
        "command-light",
    )
    for m in fallback_sequence:
        if m not in preferred:
            preferred.append(m)

    last_error: Exception | None = None
    for candidate in preferred:
        try:
            response = co.chat(message=prompt, model=candidate)
            return (response.text or "").strip()
        except Exception as e:  # noqa: BLE001 broad to allow retry loop
            # Detect sunset / removal 404 to continue; otherwise break
            msg = str(e)
            if "404" in msg and ("removed" in msg.lower() or "not found" in msg.lower()):
                print(f"[WARN] Cohere model '{candidate}' unavailable (sunset?). Trying next.")
                last_error = e
                continue
            last_error = e
            break
    print(f"[ERROR] Cohere.generate failed after fallbacks: {last_error}")
    raise last_error if last_error else RuntimeError("Unknown Cohere failure")


# ======================================================
# 🔹 Embedding Creation
# ======================================================
def create_embedding(
    text: str,
    model: str = "embed-english-v3.0",
    input_type: str = "search_document"
) -> list[float]:
    """
    Create an embedding vector for the given text.

    Args:
        text (str): The text to embed.
        model (str): The embedding model (default: "embed-english-v3.0").
        input_type (str): Type of input ("search_document", "search_query", etc.).

    Returns:
        list[float]: The embedding vector.
    """
    if not co:
        raise ConnectionError("Cohere service is not configured.")

    try:
        response = co.embed(texts=[text], model=model, input_type=input_type)
        return response.embeddings[0]
    except Exception as e:
        print(f"[ERROR] Cohere.create_embedding failed: {e}")
        raise


# ======================================================
# 🔹 Simple Self-Test (manual invocation)
# ======================================================
def _self_test():  # pragma: no cover - dev helper
    sample = "Hello from Maya test."
    try:
        print("[SELFTEST] Generating chat response...")
        resp = generate(sample)
        print("[SELFTEST] Chat OK:", resp[:120])
    except Exception as e:
        print("[SELFTEST] Chat FAILED:", e)
    try:
        print("[SELFTEST] Creating embedding...")
        emb = create_embedding(sample)
        print("[SELFTEST] Embedding length:", len(emb))
    except Exception as e:
        print("[SELFTEST] Embedding FAILED:", e)

if __name__ == "__main__":  # pragma: no cover
    _self_test()
