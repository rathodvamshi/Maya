# backend/app/services/ai_service.py

import time
import logging
import json
import threading
from typing import List, Optional, Dict, Any, Callable, Tuple

import google.generativeai as genai
import cohere
import anthropic

from app.config import settings
from app.prompt_templates import MAIN_SYSTEM_PROMPT  # legacy template retained for other uses
from app.services.prompt_composer import compose_prompt

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 AI Client Initialization
# =====================================================
gemini_keys = [key.strip() for key in settings.GEMINI_API_KEYS.split(",") if key.strip()]
current_gemini_key_index = 0
cohere_client = cohere.Client(settings.COHERE_API_KEY) if settings.COHERE_API_KEY else None
anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

# =====================================================
# 🔹 Circuit Breaker & Provider Fallback
# =====================================================
FAILED_PROVIDERS: dict[str, float] = {}
def _derive_provider_order() -> List[str]:
    # Allow env-specified order; fallback to default performance-oriented order
    if settings.AI_PROVIDER_ORDER:
        custom = [p.strip() for p in settings.AI_PROVIDER_ORDER.split(',') if p.strip()]
        valid = [p for p in custom if p in ("gemini", "cohere", "anthropic")]
        if valid:
            return valid
    # Default: fastest / cheapest first (adjust as benchmarking data refines)
    return ["gemini", "cohere", "anthropic"]

AI_PROVIDERS = _derive_provider_order()

def _is_provider_available(name: str) -> bool:
    """Check if provider is available (not in cooldown)."""
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[AI] Provider '{name}' in cooldown. Skipping.")
        return False
    return True

# =====================================================
# 🔹 Provider Helpers
# =====================================================
def _try_gemini(prompt: str) -> str:
    global current_gemini_key_index
    if not gemini_keys:
        raise RuntimeError("No Gemini API keys configured.")
    start_index = current_gemini_key_index
    while True:
        try:
            key = gemini_keys[current_gemini_key_index]
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"[Gemini] Key {current_gemini_key_index} failed: {e}")
            current_gemini_key_index = (current_gemini_key_index + 1) % len(gemini_keys)
            if current_gemini_key_index == start_index:
                raise RuntimeError("All Gemini API keys failed.")

def _try_cohere(prompt: str) -> str:
    if not cohere_client:
        raise RuntimeError("Cohere API client not configured.")
    try:
        response = cohere_client.chat(message=prompt, model="command-r-08-2024")
        return response.text
    except Exception as e:
        raise RuntimeError(f"Cohere API error: {e}")

def _try_anthropic(prompt: str) -> str:
    if not anthropic_client:
        raise RuntimeError("Anthropic API client not configured.")
    try:
        message = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # Ensure compatibility with newer API responses
        if hasattr(message, "content") and message.content:
            return message.content[0].text
        elif hasattr(message, "completion"):
            return message.completion
        else:
            raise RuntimeError("Anthropic response parsing failed.")
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")

# =====================================================
# 🔹 Main AI Response Generator
# =====================================================
def _call_with_timeout(func: Callable[[], str], timeout_s: float) -> str:
    """Run sync provider call with hard timeout using a thread.

    If the function does not complete in time, raises TimeoutError.
    This avoids blocking the whole request on a slow upstream.
    """
    result: Dict[str, Any] = {}
    exc: Dict[str, BaseException] = {}

    def runner():
        try:
            result["value"] = func()
        except BaseException as e:  # noqa: BLE001
            exc["err"] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        # Thread still running; we abandon it (daemon) and timeout.
        raise TimeoutError(f"Provider call exceeded {timeout_s}s")
    if "err" in exc:
        raise exc["err"]
    return result.get("value", "")


def _maybe_handle_introspection(
    user_prompt: str,
    profile: Optional[Dict[str, Any]],
    neo4j_facts: Optional[str],
    user_facts_semantic: Optional[List[str]],
) -> Tuple[bool, str]:
    """Detect self-knowledge queries (name, favorites, profile summary) and answer succinctly.

    Returns (handled, response). Keeps answers short (1–2 sentences) for comfort.
    """
    if not profile:
        profile = {}
    low = user_prompt.lower().strip()

    name = profile.get("name")
    favorites = profile.get("favorites", {}) or {}
    hobbies = profile.get("hobbies", []) or []

    def fmt_list(items: List[str], limit: int = 3) -> str:
        if not items:
            return ""
        cut = items[:limit]
        if len(cut) == 1:
            return cut[0]
        if len(cut) == 2:
            return f"{cut[0]} and {cut[1]}"
        return ", ".join(cut[:-1]) + f" and {cut[-1]}"

    # Name-centric queries
    if any(p in low for p in [
        "what's my name", "whats my name", "do you know my name", "do u know my name", "my name?", "tell me my name"
    ]):
        if name:
            # Differentiate question styles for a slightly more natural feel while still deterministic.
            if "do" in low:
                return True, f"Yes, your name is {name}."
            return True, f"Your name is {name}."
        return True, "I don't have your name yet. You can tell me and I'll remember it."

    # Cuisine / favorite cuisine queries
    if "what cuisine do i like" in low or "my favorite cuisine" in low or "favorite cuisine" in low:
        cuisine = favorites.get("cuisine") or favorites.get("food")
        if cuisine:
            return True, f"You enjoy {cuisine} cuisine."
        return True, "You haven't told me your favorite cuisine yet."

    # General favorites query
    if any(p in low for p in [
        "what are my favorites", "what do i like", "my favorites?", "do you know my favorites"
    ]):
        if favorites:
            limited = list(favorites.items())[:3]
            fav_str = ", ".join(f"{k}={v}" for k, v in limited)
            return True, f"Your favorites I know: {fav_str}."
        return True, "I don't have any favorites stored yet."

    # Broad self-knowledge / profile summary
    if any(p in low for p in ["what do you know about me", "what do u know about me", "what do you know of me", "what can you tell me about me"]):
        if not (name or favorites or hobbies or user_facts_semantic):
            return True, "I don't have personal details yet. You can share your name or preferences and I'll remember them."
        cuisine = favorites.get("cuisine") or favorites.get("food")
        bits: List[str] = []
        if name and cuisine:
            bits.append(f"I know your name is {name} and you enjoy {cuisine} cuisine")
        elif name:
            bits.append(f"I know your name is {name}")
        elif cuisine:
            bits.append(f"You enjoy {cuisine} cuisine")
        # Add one more favorite if available (other than cuisine)
        other_fav = None
        for k, v in favorites.items():
            if k in ("cuisine", "food"):
                continue
            other_fav = (k, v)
            break
        if other_fav:
            bits.append(f"and your {other_fav[0]} is {other_fav[1]}")
        if hobbies:
            bits.append("you like " + fmt_list(hobbies, 3))
        # Join gracefully
        summary = " ".join(bits).strip()
        if not summary.endswith('.'):
            summary += '.'
        return True, summary

    return False, ""


def get_response(
    prompt: str,
    history: Optional[List[dict]] = None,
    pinecone_context: Optional[str] = None,
    neo4j_facts: Optional[str] = None,
    state: str = "general_conversation",
    profile: Optional[Dict[str, Any]] = None,
    user_facts_semantic: Optional[List[str]] = None,
) -> str:
    """Generates AI response using multiple providers with timeout + fallback.

    Timeout strategy:
      - Primary (first provider): settings.AI_PRIMARY_TIMEOUT seconds
      - Each fallback: settings.AI_FALLBACK_TIMEOUT seconds
    """

    # Introspection shortcut handling
    handled, direct_resp = _maybe_handle_introspection(
        prompt, profile, neo4j_facts, user_facts_semantic
    )
    if handled:
        return direct_resp

    # Use new composer (falls back to legacy style if needed later)
    full_prompt = compose_prompt(
        user_message=prompt,
        state=state,
        history=history or [],
        pinecone_context=pinecone_context,
        neo4j_facts=neo4j_facts,
        profile=profile,
        user_facts_semantic=user_facts_semantic,
    )

    logger.debug("----- Full AI Prompt -----\n%s\n--------------------------", full_prompt)

    for idx, provider in enumerate(AI_PROVIDERS):
        if not _is_provider_available(provider):
            continue
        try:
            timeout_budget = settings.AI_PRIMARY_TIMEOUT if idx == 0 else settings.AI_FALLBACK_TIMEOUT
            def invoke() -> str:
                if provider == "gemini":
                    return _try_gemini(full_prompt)
                if provider == "anthropic":
                    return _try_anthropic(full_prompt)
                if provider == "cohere":
                    return _try_cohere(full_prompt)
                raise RuntimeError("Unknown provider")

            result = _call_with_timeout(invoke, timeout_budget)
            FAILED_PROVIDERS.pop(provider, None)
            # Post-processing: replace internal id tokens with friendly name if available
            if profile and profile.get("name"):
                uname = profile["name"]
                # Basic heuristic: internal ids look like User_<hex>
                import re as _re
                result = _re.sub(r"User_[0-9a-fA-F]{8,40}", uname, result)
            return result
        except TimeoutError as te:
            logger.warning(f"[AI] Provider '{provider}' timeout after {te}")
            FAILED_PROVIDERS[provider] = time.time()
        except Exception as e:
            logger.error(f"[AI] Provider '{provider}' failed: {e}")
            FAILED_PROVIDERS[provider] = time.time()

    return "❌ All AI services are currently unavailable. Please try again later."


# Backward-compatibility alias used by some modules
def generate_ai_response(prompt: str) -> str:
    return get_response(prompt)

# =====================================================
# 🔹 Summarization Utility
# =====================================================
def summarize_text(text: str) -> str:
    summary_prompt = (
        "You are an expert at summarizing conversations. "
        "Provide a concise, third-person summary of the following transcript:\n\n"
        f"---\n{text}\n---\n\nSUMMARY:"
    )
    for idx, provider in enumerate(AI_PROVIDERS):
        if not _is_provider_available(provider):
            continue
        try:
            timeout_budget = settings.AI_PRIMARY_TIMEOUT if idx == 0 else settings.AI_FALLBACK_TIMEOUT
            def invoke() -> str:
                if provider == "gemini":
                    return _try_gemini(summary_prompt)
                if provider == "anthropic":
                    return _try_anthropic(summary_prompt)
                if provider == "cohere":
                    return _try_cohere(summary_prompt)
                raise RuntimeError("Unknown provider")
            return _call_with_timeout(invoke, timeout_budget)
        except TimeoutError as te:
            logger.warning(f"[AI] Summarization provider '{provider}' timeout: {te}")
            FAILED_PROVIDERS[provider] = time.time()
        except Exception as e:
            logger.error(f"[AI] Summarization failed with '{provider}': {e}")
            FAILED_PROVIDERS[provider] = time.time()
    return "❌ Failed to generate summary. All AI services unavailable."

# =====================================================
# 🔹 Fact Extraction Utility
# =====================================================
def extract_facts_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract structured facts (entities + relationships) from a conversation transcript.
    Returns a JSON dict with 'entities' and 'relationships'.
    """
    extraction_prompt = f"""
    Analyze the following transcript. Your only task is to extract entities and relationships.
    Respond with ONLY a valid JSON object. Do not include markdown, explanations, or any text
    outside of the JSON structure. If no facts are found, return {{"entities": [], "relationships": []}}.

    Transcript:
    ---
    {text}
    ---
    """
    try:
        # Use the providers most suited for structured output
        fact_sequence = [
            ("cohere", _try_cohere),
            ("gemini", _try_gemini),
            ("anthropic", _try_anthropic),
        ]
        raw_response = ""
        for idx, (name, func) in enumerate(fact_sequence):
            if not _is_provider_available(name):
                continue
            timeout_budget = settings.AI_PRIMARY_TIMEOUT if idx == 0 else settings.AI_FALLBACK_TIMEOUT
            try:
                raw_response = _call_with_timeout(lambda: func(extraction_prompt), timeout_budget)
                FAILED_PROVIDERS.pop(name, None)
                if raw_response:
                    break
            except TimeoutError as te:
                logger.warning(f"Fact extraction provider '{name}' timeout: {te}")
                FAILED_PROVIDERS[name] = time.time()
            except Exception as e:
                logger.warning(f"Fact extraction attempt failed for provider {name}: {e}")
                FAILED_PROVIDERS[name] = time.time()

        if not raw_response:
            raise RuntimeError("All fact-extraction providers failed.")

        # Attempt robust JSON parsing
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start != -1 and end != -1:
            json_str = raw_response[start:end + 1]
            return json.loads(json_str)
        else:
            logger.warning(f"Fact extraction returned no valid JSON. Raw: {raw_response}")
            return {"entities": [], "relationships": []}

    except Exception as e:
        logger.error(f"Failed to extract facts from text: {e}")
        return {"entities": [], "relationships": []}
