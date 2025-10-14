# backend/app/services/gemini.py

import google.generativeai as genai
from google.api_core import exceptions
from app.config import settings

# Track the current API key index
current_key_index = 0
api_keys = [key.strip() for key in (settings.GEMINI_API_KEYS or "").split(",") if key.strip()]
print(f"[Gemini Debug] Loaded API keys: {api_keys}")

def _configure_gemini(api_key: str):
    """Helper to configure Gemini with a given API key."""
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash-latest")
    except Exception as e:
        print(f"❌ Failed to configure Gemini with API key: {e}")
        return None

def generate_gemini_response(prompt: str) -> str:
    """
    Generates a response from the Gemini AI model.
    Supports multiple API keys with automatic failover.
    """
    global current_key_index
    if not api_keys:
        return "❌ Error: No Gemini API keys are configured."

    start_index = current_key_index
    attempts = 0
    max_attempts = len(api_keys)
    while attempts < max_attempts:
        key_to_try = api_keys[current_key_index]
        model = _configure_gemini(key_to_try)

        if not model:
            attempts += 1
            current_key_index = (current_key_index + 1) % len(api_keys)
            continue

        try:
            response = model.generate_content(prompt)
            return response.text
        except exceptions.ResourceExhausted:
            print(f"⚠️ API key at index {current_key_index} is rate-limited. Trying next key...")
            attempts += 1
            current_key_index = (current_key_index + 1) % len(api_keys)
        except Exception as e:
            print(f"❌ Error while generating AI response: {e}")
            attempts += 1
            current_key_index = (current_key_index + 1) % len(api_keys)
    return "🚦 All available Gemini API keys failed or are rate-limited. Please try again later."
