# backend/app/services/gemini_service.py

import google.generativeai as genai
from app.config import settings

# --- Global State for Key Rotation ---
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(',') if key.strip()]
current_gemini_key_index = 0

def generate(prompt: str) -> str:
    """
    Attempts to get a response from Gemini, rotating keys on failure.
    """
    global current_gemini_key_index
    if not gemini_keys:
        raise ConnectionError("Gemini API keys are not configured.")

    start_index = current_gemini_key_index
    while True:
        try:
            key_to_try = gemini_keys[current_gemini_key_index]
            genai.configure(api_key=key_to_try)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            print(f"⚠️ Gemini key at index {current_gemini_key_index} failed.")
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)
            if current_gemini_key_index == start_index:
                raise RuntimeError(f"All Gemini API keys failed. Last error: {e}")

def create_embedding(text: str) -> list[float]:
    """Creates an embedding using Google's text-embedding-004 model."""
    # Note: Key rotation is not applied here for simplicity, but could be added.
    genai.configure(api_key=gemini_keys[0])
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document"
    )
    return result['embedding']