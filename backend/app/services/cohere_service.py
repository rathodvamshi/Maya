# backend/app/services/cohere_service.py

import cohere
from app.config import settings

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
def generate(prompt: str, model: str = "command-r") -> str:
    """
    Generate a conversational response using Cohere's chat API.

    Args:
        prompt (str): The user input or system prompt.
        model (str): Cohere model name (default: "command-r").

    Returns:
        str: The AI-generated response text.
    """
    if not co:
        raise ConnectionError("Cohere service is not configured.")

    try:
        response = co.chat(message=prompt, model=model)
        return response.text.strip()
    except Exception as e:
        print(f"[ERROR] Cohere.generate failed: {e}")
        raise


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
