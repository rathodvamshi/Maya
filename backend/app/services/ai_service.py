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
from app.services.emotion_service import (
    detect_emotion,
    enrich_with_emojis,
    build_persona_directive,
    count_emojis,
)
from app.services import memory_store
from app.services.telemetry import log_interaction_event, classify_complexity
from app.services.behavior_tracker import update_behavior_from_event, get_inferred_preferences
from app.services import metrics
from app.services.redis_service import record_provider_latency, record_provider_win, fetch_adaptive_stats

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Post-Processing Helpers (Suggestion Enforcement)
# =====================================================
SUGGESTION_PREFIX = "➝"
def _fire_and_forget(coro):  # pragma: no cover (utility)
    """Schedule coroutine without awaiting.

    If there's an active running loop, create a task. If not, run it synchronously
    (blocks briefly) to avoid RuntimeWarning about un-awaited coroutines in test env.
    """
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(coro)
                return
        except RuntimeError:
            pass
        # No running loop -> run synchronously
        asyncio.run(coro)
    except Exception:  # noqa: BLE001
        pass

# =====================================================
# 🔹 User Token Replacement Helper
# =====================================================
def replace_internal_user_tokens(text: str, profile: Optional[Dict[str, Any]]) -> str:
    """Replace model-emitted internal placeholders like User_<hex>.

    If profile has a name -> substitute with that exact name.
    Else substitute with a deterministic friendly alias derived from user_id hash so it stays stable.
    """
    import re as _re, hashlib as _hashlib
    pattern = _re.compile(r"User_[0-9a-fA-F]{8,40}")
    if not pattern.search(text):
        return text
    name = None
    user_id = None
    if isinstance(profile, dict):
        name = profile.get("name")
        user_id = profile.get("user_id") or profile.get("id") or profile.get("_id")
    if name:
        return pattern.sub(str(name), text)
    aliases = [
        "buddy", "friend", "rockstar", "champ", "pal", "legend", "mate", "star", "trailblazer", "ace"
    ]
    idx = 0
    if user_id:
        h = _hashlib.sha256(str(user_id).encode()).hexdigest()
        idx = int(h, 16) % len(aliases)
    alias = aliases[idx]
    # Capitalize if appears after greeting Hello/Hi etc.
    def _sub(m: _re.Match) -> str:  # noqa: ANN001
        return alias
    return pattern.sub(_sub, text)

def strip_existing_suggestions(text: str) -> str:
    """Ensure at most two suggestion lines (those starting with the arrow) are retained."""
    lines = text.splitlines()
    kept = []
    suggestion_count = 0
    for ln in lines:
        raw = ln.strip()
        if raw.startswith(SUGGESTION_PREFIX):
            if suggestion_count < 2:
                kept.append(ln)
                suggestion_count += 1
            # extra suggestions discarded silently
        else:
            kept.append(ln)
    return "\n".join(kept)

def compute_suggestions(base_text: str, user_prompt: str, profile: Optional[Dict[str, Any]]) -> List[str]:
    """Return up to two suggestion lines (each with arrow prefix) or empty list.

    Used by both append mode (non-stream) and streaming path.
    """
    from app.config import settings as _settings  # local import to avoid circular during tests
    from app.services import memory_store as _memory_store
    if not _settings.ENABLE_SUGGESTIONS:
        return []
    low_user = user_prompt.lower()
    if any(p in low_user for p in ["no suggestions", "stop suggestions", "don't give suggestions", "dont give suggestions"]):
        return []

    # If text already has suggestions, we respect them (handled in append wrapper) -> return empty so wrapper can keep existing.
    if SUGGESTION_PREFIX in base_text:
        return []

    # Determine quick vs deep answer (rough heuristic length check excluding suggestion arrows)
    plain_answer = base_text.strip()
    answer_char_len = len(plain_answer)
    answer_is_short = answer_char_len < 220  # configurable heuristic

    low = user_prompt.lower()
    raw_candidates: List[str] = []
    if any(k in low for k in ["how do i", "steps", "guide", "tutorial"]):
        if answer_is_short:
            raw_candidates += [
                "Want a detailed step-by-step checklist?",
                "Need a quick rationale for each step?",
            ]
        else:
            raw_candidates += [
                "Want a concise summary of the steps?",
                "Need a minimal checklist version?",
            ]
    elif any(k in low for k in ["what is", "explain", "define", "meaning of"]):
        if answer_is_short:
            raw_candidates += ["Want a deeper breakdown with examples?", "Should I compare it to a related concept?"]
        else:
            raw_candidates += ["Want a quick summary version?", "Need a real-world analogy?"]
    elif any(k in low for k in ["recommend", "suggest", "movie", "book", "music", "song", "playlist"]):
        raw_candidates += ["Want more options in another style?", "Should I save these preferences for later?"]
    elif any(k in low for k in ["hi", "hello", "hey"]):
        raw_candidates += ["Want a fun fact to start?", "Need help with something specific today?"]
    else:
        if answer_is_short:
            raw_candidates += ["Want me to expand this?", "Need related tips or resources?"]
        else:
            raw_candidates += ["Want a concise summary?", "Need an example to solidify it?"]

    # Derive preferred tone (profile preference) for style adaptation
    tone_pref = None
    if isinstance(profile, dict):
        prefs = profile.get("preferences") or {}
        if isinstance(prefs, dict):
            tone_pref = (prefs.get("tone") or "").lower() or None

    def _adapt_phrase(phrase: str) -> str:
        base = phrase.strip()
        if not tone_pref:
            return base
        # Formal style: replace casual stems, avoid emojis, more polite modal forms
        if tone_pref in {"formal"}:
            repl_map = {
                "want you": "would you like me",
                "want a": "would you like a",
                "want an": "would you like an",
                "want": "would you like",
                "need": "would you like",
                "should i": "shall I",
            }
            low = base.lower()
            for k, v in repl_map.items():
                if k in low:
                    # crude whole-substring replacement preserving capitalization of first letter
                    low = low.replace(k, v)
            # Reconstruct capitalization (first char upper)
            out = low[0].upper() + low[1:] if low else low
            if not out.endswith("?"):
                out += "?"
            return out
        # Playful / enthusiastic / supportive tones can allow light emoji accent
        elif tone_pref in {"playful", "enthusiastic"}:
            if not any(ch in base for ch in ["🙂", "😄", "😉", "🤗", "✨"]):
                if len(base) < 70:
                    base = base.rstrip("?")  # remove existing ? to append nicely
                    base += "? 😄"
            return base
        elif tone_pref in {"supportive", "warm"}:
            # Softer phrasing
            if base.lower().startswith("want"):
                base = "Would it help if I " + base[4:].lstrip()
            if not any(ch in base for ch in ["💛", "🤗", "🌱"]):
                if len(base) < 72:
                    base = base.rstrip("?") + "? 💛"
            return base
        elif tone_pref in {"concise"}:
            # Keep extremely short; remove fillers
            base = base.replace("Would you like", "Want").replace("Need", "Need")
            # Trim to first question mark or add one
            if len(base) > 55:
                base = base[:55].rstrip(" .,")
            if not base.endswith("?"):
                base += "?"
            return base
        return base

    # Memory-aware dedupe: filter out lines recently used
    user_id = None
    if isinstance(profile, dict):
        user_id = profile.get("user_id") or profile.get("id") or profile.get("_id")
    recent: List[str] = []
    if user_id:
        try:
            import asyncio as _asyncio
            async def _fetch():
                try:
                    return await _memory_store.get_recent_suggestions(str(user_id), limit=_settings.SUGGESTION_HISTORY_WINDOW)
                except Exception:
                    return []
            try:
                loop = _asyncio.get_running_loop()
                if loop.is_running():
                    # schedule but cannot use result in sync context
                    _fire_and_forget(_fetch())
                else:
                    recent = _asyncio.run(_fetch())
            except RuntimeError:
                recent = _asyncio.run(_fetch())
        except Exception:  # noqa: BLE001
            recent = []
    # Basic filter by exact text match (case insensitive)
    recent_lower = {r.lower() for r in recent}
    # Adapt phrases before filtering so dedupe applies to final styled text
    adapted_candidates = [_adapt_phrase(c) for c in raw_candidates]
    filtered = [c for c in adapted_candidates if c.lower() not in recent_lower]
    # If everything was filtered, fall back to original list to avoid empty set
    if not filtered:
        filtered = raw_candidates

    # Deduplicate within the candidate list
    final_candidates: List[str] = []
    seen_local = set()
    for c in filtered:
        key = c.lower()
        if key in seen_local:
            continue
        seen_local.add(key)
        final_candidates.append(c)

    suggestions: List[str] = []
    for cand in final_candidates:
        if len(suggestions) >= 2:
            break
        suggestions.append(f"{SUGGESTION_PREFIX} {cand}")

    if not suggestions:
        return []

    if user_id:
        raw_store = [s[len(SUGGESTION_PREFIX):].strip() for s in suggestions]
        try:
            from app.services import memory_store as _ms
            _fire_and_forget(_ms.push_suggestions(str(user_id), raw_store))  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            pass
    return suggestions


def append_suggestions_if_missing(base_text: str, user_prompt: str, profile: Optional[Dict[str, Any]]) -> str:
    """Wrapper for non-stream flows: append suggestions to text if missing."""
    if SUGGESTION_PREFIX in base_text:
        return strip_existing_suggestions(base_text)
    suggestions = compute_suggestions(base_text, user_prompt, profile)
    if not suggestions:
        return base_text
    return base_text.rstrip() + "\n" + "\n".join(suggestions)

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
_ADAPTIVE_LAST_REORDER: float = 0.0
_ADAPTIVE_MIN_INTERVAL = 30.0  # seconds between reorder attempts

def _derive_provider_order() -> List[str]:
    """Return current provider preference order.

    Priority: explicit env override > adaptive ordering > default static order.
    Adaptive ordering uses recent latency histogram + win counters to rank providers.
    """
    # 1. Explicit env override
    if settings.AI_PROVIDER_ORDER:
        custom = [p.strip() for p in settings.AI_PROVIDER_ORDER.split(',') if p.strip()]
        valid = [p for p in custom if p in ("gemini", "cohere", "anthropic")]
        if valid:
            return valid

    # 2. Adaptive ordering (only if sufficient data & interval passed)
    try:
        import time as _t
        global _ADAPTIVE_LAST_REORDER
        now = _t.time()
        if now - _ADAPTIVE_LAST_REORDER < _ADAPTIVE_MIN_INTERVAL:
            raise RuntimeError("Adaptive interval not reached")
        from app.services import metrics as _m
        snap = _m.snapshot()
        counters = snap.get("counters", {})
        hist = snap.get("histograms", {})
        scores: List[Tuple[float, str]] = []
        for prov in ["gemini", "cohere", "anthropic"]:
            win_key = f"chat.hedge.win.provider.{prov}"
            wins = counters.get(win_key, 0)
            # use provider.latency.<prov> histogram to approximate mean
            h_name = f"provider.latency.{prov}"
            if h_name in hist and hist[h_name].get("count"):
                avg = hist[h_name]["sum"] / hist[h_name]["count"]
            else:
                avg = 1500.0  # pessimistic default
            # Score: lower latency better, add small bonus for more wins
            score = avg - (wins * 10)  # 10ms credit per win
            scores.append((score, prov))
        scores.sort()
        ordered = [p for _, p in scores]
        # keep only providers actually configured/available clients
        filtered: List[str] = []
        for p in ordered:
            if p == "gemini" and gemini_keys:
                filtered.append(p)
            elif p == "cohere" and cohere_client:
                filtered.append(p)
            elif p == "anthropic" and anthropic_client:
                filtered.append(p)
        if filtered:
            _ADAPTIVE_LAST_REORDER = now
            return filtered
    except Exception:
        pass

    # 3. Default order
    return ["gemini", "cohere", "anthropic"]

AI_PROVIDERS = _derive_provider_order()

def _is_provider_available(name: str) -> bool:
    """Check if provider is available (not in cooldown)."""
    failure_time = FAILED_PROVIDERS.get(name)
    if failure_time and (time.time() - failure_time) < settings.AI_PROVIDER_FAILURE_TIMEOUT:
        logger.warning(f"[AI] Provider '{name}' in cooldown. Skipping.")
        return False
    # Recovery path (if previously failed & now outside cooldown) -> emit recovery metric
    if failure_time and (time.time() - failure_time) >= settings.AI_PROVIDER_FAILURE_TIMEOUT:
        try:
            from app.services import metrics as _m
            _m.incr(f"chat.provider.recovery.{name}")
        except Exception:  # noqa: BLE001
            pass
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

# =====================================================
# 🔹 Async Provider Wrappers (non-blocking orchestration)
# =====================================================
async def _invoke_provider(provider: str, prompt: str) -> str:
    """Invoke the underlying sync provider helper in a worker thread.

    We keep the existing sync _try_* functions for reuse in other sync utilities
    (e.g., summarization) but for the main chat path we shift to an async model
    so hedged / parallel execution does not block the event loop.
    """
    import asyncio
    if provider == "gemini":
        return await asyncio.to_thread(_try_gemini, prompt)
    if provider == "cohere":
        return await asyncio.to_thread(_try_cohere, prompt)
    if provider == "anthropic":
        return await asyncio.to_thread(_try_anthropic, prompt)
    raise RuntimeError(f"Unknown provider {provider}")


async def _invoke_with_timeout(provider: str, prompt: str, timeout_s: float) -> str:
    import asyncio
    return await asyncio.wait_for(_invoke_provider(provider, prompt), timeout=timeout_s)


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


async def get_response(
    prompt: str,
    history: Optional[List[dict]] = None,
    pinecone_context: Optional[str] = None,
    neo4j_facts: Optional[str] = None,
    state: str = "general_conversation",
    profile: Optional[Dict[str, Any]] = None,
    user_facts_semantic: Optional[List[str]] = None,
    persistent_memories: Optional[List[Dict[str, Any]]] = None,
    suppress_suggestions: bool = False,
    session_id: Optional[str] = None,
) -> str:
    """Generates AI response using multiple providers with timeout + fallback (async version).

    This function was converted to async so that downstream coroutine based utilities
    (behavior updates, redis interactions, emotion trend pushes, telemetry hooks)
    can be awaited or scheduled without relying on event-loop introspection hacks.

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

    # Lightweight emotion detection BEFORE composing the prompt so we can append persona directive
    # Per-user preference overrides (if present)
    pref_enable_emotion = None
    pref_enable_emoji = None
    if isinstance(profile, dict):
        prefs = profile.get("preferences") or {}
        val = str(prefs.get("emotion_persona") or "").lower()
        if val in {"on", "off"}:
            pref_enable_emotion = (val == "on")
        val2 = str(prefs.get("emoji") or "").lower()
        if val2 in {"on", "off"}:
            pref_enable_emoji = (val2 == "on")

    use_emotion = (pref_enable_emotion if pref_enable_emotion is not None else settings.ENABLE_EMOTION_PERSONA)
    use_emoji = (pref_enable_emoji if pref_enable_emoji is not None else settings.ENABLE_EMOJI_ENRICHMENT)

    if use_emotion:
        emotion_result = detect_emotion(prompt)
        # Retrieve trend to evaluate escalation
        recent_emotions: List[str] = []
        # (Escalation trend retrieval handled below now that we are async.)
    else:
        class _Dummy:  # noqa: D401
            emotion = "neutral"; confidence = 0.0; tone = "neutral"; lead_emoji = ""; palette = ["🙂"]
        emotion_result = _Dummy()  # type: ignore

    # Advanced positive memory heuristic: prefer most recent positive-sounding message in history that mentions a hobby or favorite
    last_positive_memory = None
    if profile:
        try:
            favorites = (profile.get("favorites") or {}) if isinstance(profile, dict) else {}
            hobbies = (profile.get("hobbies") or []) if isinstance(profile, dict) else []
            # Scan history backwards for a line containing 'love', 'enjoy', 'like'
            if history:
                for h in reversed(history):
                    txt = (h.get("text") or h.get("content") or "").lower()
                    if any(k in txt for k in ["love", "enjoy", "like", "fun"]):
                        snippet = txt[:120]
                        last_positive_memory = snippet
                        break
            if not last_positive_memory:
                if hobbies:
                    last_positive_memory = f"You enjoy {hobbies[-1]}"
                elif favorites.get("cuisine"):
                    last_positive_memory = f"You like {favorites.get('cuisine')} cuisine"
        except Exception:  # noqa: BLE001
            pass

    # Escalation check (async)
    escalation = False
    if use_emotion and getattr(emotion_result, "emotion", "neutral") in {"sad", "angry", "anxious"}:
        try:
            # Attempt to pull recent emotions via memory_store async API if available
            if hasattr(memory_store, "redis_client"):
                key = f"user:{(profile or {}).get('user_id')}:emotions"
                try:
                    recent = await memory_store.redis_client.lrange(key, -settings.EMOTION_TREND_WINDOW, -1)  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001
                    recent = []
                if recent:
                    streak = 0
                    for lbl in reversed(recent):
                        if lbl == getattr(emotion_result, "emotion", "neutral"):
                            streak += 1
                        else:
                            break
                    if streak >= settings.EMOTION_ESCALATION_THRESHOLD:
                        escalation = True
        except Exception:  # noqa: BLE001
            escalation = False

    tone_override = None
    if isinstance(profile, dict):
        prefs = profile.get("preferences") or {}
        tval = prefs.get("tone")
        if isinstance(tval, str) and tval.strip():
            tone_override = tval.strip()[:40]

    # ------- Inferred Preferences Caching (LRU + Redis-first) -------
    inferred_prefs: Dict[str, Any] = {}

    # Module-level LRU cache
    global _INFER_PREFS_CACHE  # type: ignore  # defined below if not yet
    try:
        _INFER_PREFS_CACHE  # type: ignore[name-defined]
    except NameError:  # noqa: BLE001
        _INFER_PREFS_CACHE = {}

    _INFER_PREFS_TTL = 120  # seconds
    def _now_ts():
        import time as _t; return int(_t.time())

    def _sync_fetch(uid: str) -> Dict[str, Any]:
        import asyncio
        async def _runner():
            try:
                return await get_inferred_preferences(uid)
            except Exception:
                return {}
        try:
            loop = asyncio.get_running_loop()
            # If already in running loop, skip (avoid nested) -> return empty (fallback)
            if loop.is_running():
                return {}
        except RuntimeError:
            pass
        try:
            return asyncio.run(_runner())
        except Exception:
            return {}

    user_id_for_infer = None
    if isinstance(profile, dict):
        user_id_for_infer = profile.get("user_id") or profile.get("id") or profile.get("_id")
    cache_source = None
    if user_id_for_infer:
        uid = str(user_id_for_infer)
        # 1. In-process LRU check
        entry = _INFER_PREFS_CACHE.get(uid)
        if entry and entry[0] > _now_ts():
            inferred_prefs = entry[1]
            cache_source = "lru"
        else:
            # 2. Redis prefetched key
            try:
                from app.services.redis_service import get_prefetched_data, set_prefetched_data  # type: ignore
                import asyncio as _asyncio
                cache_key = f"user:{uid}:inferred_prefs:v1"
                redis_data = None
                try:
                    async def _g():  # fetch helper
                        try:
                            return await get_prefetched_data(cache_key)  # type: ignore
                        except Exception:
                            return None
                    try:
                        loop2 = _asyncio.get_running_loop()
                        if loop2.is_running():
                            redis_data = await _g()
                        else:
                            redis_data = _asyncio.run(_g())
                    except RuntimeError:
                        redis_data = _asyncio.run(_g())
                except Exception:
                    redis_data = None

                if isinstance(redis_data, dict) and redis_data:
                    inferred_prefs = redis_data
                    _INFER_PREFS_CACHE[uid] = (_now_ts() + _INFER_PREFS_TTL, redis_data)
                    cache_source = "redis"
                else:
                    # Compute and then store
                    computed = _sync_fetch(uid) or {}
                    inferred_prefs = computed
                    if computed:
                        _INFER_PREFS_CACHE[uid] = (_now_ts() + _INFER_PREFS_TTL, computed)
                        cache_source = "compute"
                        try:  # best-effort async store
                            async def _s():
                                try:
                                    await set_prefetched_data(cache_key, computed, ttl_seconds=_INFER_PREFS_TTL)  # type: ignore
                                except Exception:
                                    pass
                            try:
                                loop2 = _asyncio.get_running_loop()
                                if loop2.is_running():
                                    loop2.create_task(_s())
                                else:
                                    _asyncio.run(_s())
                            except RuntimeError:
                                _asyncio.run(_s())
                        except Exception:
                            pass
            except Exception:
                inferred_prefs = _sync_fetch(uid) or {}
                if inferred_prefs and cache_source is None:
                    cache_source = "compute"

    # Instrumentation log for cache usage
    try:
        if user_id_for_infer and cache_source:
            logger.info(
                "inferred_prefs_cache | user=%s source=%s detail=%s tone=%s depth_bias=%s",
                user_id_for_infer,
                cache_source,
                inferred_prefs.get("detail_level"),
                inferred_prefs.get("tone_preference_inferred"),
                inferred_prefs.get("depth_bias"),
            )
            metrics.incr(f"inferred_prefs.source.{cache_source}")
            if "detail_level" in inferred_prefs:
                metrics.incr(f"inferred_prefs.detail.{inferred_prefs['detail_level']}")
    except Exception:  # noqa: BLE001
        pass
    persona_directive = build_persona_directive(
        emotion_result,
        last_positive_memory,
        escalation=escalation,
        tone_override=tone_override,
    ) if use_emotion else ""

    # Augment persona directive with inferred preferences if present (and not duplicative)
    if inferred_prefs:
        try:
            detail_level = inferred_prefs.get("detail_level")
            tone_pref_inferred = inferred_prefs.get("tone_preference_inferred")
            depth_bias = inferred_prefs.get("depth_bias")
            add_bits = []
            if detail_level in {"deep", "concise"}:
                if detail_level == "deep":
                    add_bits.append("User historically engages well with deeper explanations—offer a succinct answer first then optionally one compact deeper nuance.")
                elif detail_level == "concise":
                    add_bits.append("User tends to prefer concise replies—opt for brevity and only elaborate if they ask.")
            if tone_pref_inferred and (tone_override or "")[:20].lower() != tone_pref_inferred.lower():
                add_bits.append(f"Historical implicit tone preference: {tone_pref_inferred}. Subtly bias wording toward this without stating it.")
            if depth_bias is not None and isinstance(depth_bias, (int, float)):
                # No direct instruction; depth_bias captured by detail_level already; optional future refinement
                pass
            if add_bits:
                persona_directive = f"{persona_directive} {' '.join(add_bits)}".strip()
        except Exception:  # noqa: BLE001
            pass

    # Fire-and-forget: push emotion into trend list (only if feature enabled and non-neutral)
    if settings.ENABLE_EMOTION_PERSONA:
        try:
            if getattr(emotion_result, "emotion", "neutral") in {"sad", "angry", "anxious"}:
                user_id_for_trend = None
                if isinstance(profile, dict):
                    user_id_for_trend = profile.get("user_id") or profile.get("id") or profile.get("_id")
                if user_id_for_trend:
                    try:
                        await memory_store.push_emotion_label(str(user_id_for_trend), emotion_result.emotion)  # type: ignore[arg-type]
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass

    # Use new composer (falls back to legacy style if needed later). We piggyback persona directive
    # by appending it to the user message so providers stay stateless.
    augmented_user_prompt = f"{prompt}\n\n[Persona Guidance]\n{persona_directive}" if persona_directive else prompt
    full_prompt = compose_prompt(
        user_message=augmented_user_prompt,
        state=state,
        history=history or [],
        pinecone_context=pinecone_context,
        neo4j_facts=neo4j_facts,
        profile=profile,
        user_facts_semantic=user_facts_semantic,
        persistent_memories=persistent_memories,
    )

    logger.debug("----- Full AI Prompt -----\n%s\n--------------------------", full_prompt)

    start_total = time.time()
    try:
        from app.services import metrics as _m
        _m.incr("chat.requests.total")
    except Exception:  # noqa: BLE001
        pass

    provider: Optional[str] = None
    result: Optional[str] = None

    # Periodically refresh adaptive provider ordering (no-op if interval not reached)
    try:
        global AI_PROVIDERS
        AI_PROVIDERS = _derive_provider_order()
    except Exception:  # noqa: BLE001
        pass

    # ---------------- Hedged Parallel Branch (async) ----------------
    if settings.AI_ENABLE_HEDGED and len(AI_PROVIDERS) > 1:
        import asyncio as _asyncio
        import asyncio  # typing alias
        start_hedge = time.time()
        done_result: Optional[Tuple[str, str]] = None
        active_tasks: dict[str, asyncio.Task] = {}

        async def _run_provider_async(p: str, budget: float) -> None:
            nonlocal done_result
            if done_result is not None:
                return
            try:
                text = await _invoke_with_timeout(p, full_prompt, budget)
                if done_result is None:
                    done_result = (p, text)
            except Exception as e:  # noqa: BLE001
                FAILED_PROVIDERS[p] = time.time()
                logger.warning(f"[AI] Hedged provider {p} failed: {e}")

        # Fire primary immediately
        primary = AI_PROVIDERS[0]
        if _is_provider_available(primary):
            active_tasks[primary] = _asyncio.create_task(_run_provider_async(primary, settings.AI_PRIMARY_TIMEOUT))

        async def _launch_hedges():
            # Conditional hedge: earliest of fixed delay or dynamic threshold
            dynamic_threshold = settings.AI_PRIMARY_TIMEOUT * 0.30
            fixed_delay = settings.AI_HEDGE_DELAY_MS / 1000.0
            wait_time = min(fixed_delay, dynamic_threshold)
            await _asyncio.sleep(wait_time)
            for p in AI_PROVIDERS[1:settings.AI_MAX_PARALLEL]:
                if done_result is not None:
                    break
                if not _is_provider_available(p):
                    continue
                active_tasks[p] = _asyncio.create_task(_run_provider_async(p, settings.AI_FALLBACK_TIMEOUT))
                try:
                    from app.services import metrics as _m
                    _m.incr("chat.hedge.launch")
                    _m.set_gauge("chat.hedge.inflight", len(active_tasks))
                except Exception:  # noqa: BLE001
                    pass

        hedge_task = _asyncio.create_task(_launch_hedges())

        while True:
            if done_result is not None:
                for t in active_tasks.values():
                    if not t.done():
                        t.cancel()
                if not hedge_task.done():
                    hedge_task.cancel()
                provider, result = done_result
                FAILED_PROVIDERS.pop(provider, None)
                try:
                    from app.services import metrics as _m
                    _m.incr("chat.hedge.enabled")
                    _m.incr(f"chat.hedge.win.provider.{provider}")
                    win_ms = int((time.time() - start_hedge) * 1000)
                    _m.record_hist("chat.hedge.win_latency_ms", win_ms)
                    _m.set_gauge("chat.hedge.inflight", 0)
                    # Persist win + latency for cross-restart adaptive ordering
                    _fire_and_forget(record_provider_win(provider))
                    _fire_and_forget(record_provider_latency(provider, win_ms))
                except Exception:  # noqa: BLE001
                    pass
                break
            if all(t.done() for t in active_tasks.values()) and hedge_task.done():
                break
            await _asyncio.sleep(0.01)

    # ---------------- Sequential Fallback Branch (async) ----------------
    if result is None:
        import asyncio as _asyncio
        for idx, p in enumerate(AI_PROVIDERS):
            if not _is_provider_available(p):
                continue
            try:
                budget = settings.AI_PRIMARY_TIMEOUT if idx == 0 else settings.AI_FALLBACK_TIMEOUT
                candidate = await _invoke_with_timeout(p, full_prompt, budget)
                FAILED_PROVIDERS.pop(p, None)
                provider, result = p, candidate
                break
            except Exception as e:  # Includes TimeoutError via asyncio.wait_for
                logger.warning(f"[AI] Provider '{p}' failed in sequential path: {e}")
                FAILED_PROVIDERS[p] = time.time()

    if result is None or provider is None:
        total_ms = int((time.time() - start_total) * 1000)
        logger.error(f"[AI] All providers failed total_latency_ms={total_ms}")
        return "❌ All AI services are currently unavailable. Please try again later."

    # ---------------- Unified Post-processing ----------------
    try:
        result = replace_internal_user_tokens(result, profile)
    except Exception:  # noqa: BLE001
        pass
    total_ms = int((time.time() - start_total) * 1000)
    logger.info(f"[AI] Provider={provider} success total_latency_ms={total_ms}")
    try:
        from app.services import metrics as _m
        _m.record_hist(f"provider.latency.{provider}", total_ms)
        _fire_and_forget(record_provider_latency(provider, total_ms))
    except Exception:  # noqa: BLE001
        pass

    if use_emoji:
        try:
            existing = count_emojis(result)
            if existing < settings.EMOJI_MAX_TOTAL and use_emoji:
                budget = max(settings.EMOJI_MAX_AUTO_ADD - existing, 0)
                if budget > 0:
                    result = enrich_with_emojis(result, emotion_result, max_new=budget, hard_cap=settings.EMOJI_MAX_TOTAL)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            pass

    if not suppress_suggestions:
        try:
            before = result
            result = append_suggestions_if_missing(result, prompt, profile)
            if result is not before and SUGGESTION_PREFIX in result:
                try:
                    sug_lines = [l.strip() for l in result.splitlines() if l.strip().startswith(SUGGESTION_PREFIX)][-2:]
                    tone_pref = None
                    if isinstance(profile, dict):
                        prefs = profile.get("preferences") or {}
                        if isinstance(prefs, dict):
                            tone_pref = (prefs.get("tone") or "").lower() or None
                    logger.info(
                        "suggestions_meta | mode=inline tone=%s s1=%s s2=%s", tone_pref, sug_lines[0] if sug_lines else None, sug_lines[1] if len(sug_lines) > 1 else None
                    )
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass

    try:
        logger.info(
            "chat_response_meta | provider=%s emotion=%s conf=%.2f escalation=%s emojis_final=%d",
            provider,
            getattr(emotion_result, "emotion", "neutral"),
            getattr(emotion_result, "confidence", 0.0),
            escalation,
            count_emojis(result),
        )
    except Exception:  # noqa: BLE001
        pass

    try:
        sug_lines = [l.strip() for l in result.splitlines() if l.strip().startswith(SUGGESTION_PREFIX)][-2:]
        emotion_payload = {
            "label": getattr(emotion_result, "emotion", None),
            "confidence": getattr(emotion_result, "confidence", None),
        } if use_emotion else None
        user_id_for_log = None
        if isinstance(profile, dict):
            user_id_for_log = profile.get("user_id") or profile.get("id") or profile.get("_id")
        complexity = classify_complexity(prompt, result)
        try:
            from app.services import metrics as _m
            _m.incr("chat.responses.total")
            _m.incr(f"chat.responses.by_provider.{provider}")
            if complexity:
                _m.incr(f"complexity.{complexity}")
        except Exception:  # noqa: BLE001
            pass
        # Persona best-friend layer (post-processing) if enabled
        try:
            if settings.ENABLE_PERSONA_RESPONSE:
                from app.services.persona_response import generate_response as _persona_gen
                user_id_for_log = user_id_for_log or (profile or {}).get("user_id")  # reuse id if available
                persona_style = getattr(settings, "PERSONA_STYLE", "best_friend")
                # Confidence-based neutral fallback: if low confidence, suppress emotion-specific template
                persona_emotion = getattr(emotion_result, "emotion", "neutral")
                try:
                    if getattr(emotion_result, "confidence", 0.0) < settings.ADV_EMOTION_CONFIDENCE_THRESHOLD:
                        persona_emotion = "neutral"
                except Exception:
                    pass
                persona_result = await _persona_gen(
                    prompt,
                    emotion=persona_emotion,
                    user_id=str(user_id_for_log) if user_id_for_log else None,
                    base_ai_text=result,
                    style=persona_style,
                    confidence=getattr(emotion_result, "confidence", None),
                    second_emotion=None,  # placeholder for future advanced multi-label
                )
                if persona_result:
                    result = persona_result
        except Exception:  # noqa: BLE001
            pass
        log_interaction_event(
            user_id=user_id_for_log,
            session_id=session_id,
            user_message=prompt,
            assistant_answer=result,
            emotion=emotion_payload,
            tone=getattr(emotion_result, "tone", None),
            suggestions=sug_lines,
            provider=provider,
        )
        if user_id_for_log:
            try:
                await update_behavior_from_event(
                    user_id=str(user_id_for_log),
                    complexity=complexity,
                    answer_chars=len(result),
                    tone_used=getattr(emotion_result, "tone", None),
                )
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    return result


# Backward-compatibility alias used by some modules
async def generate_ai_response(prompt: str) -> str:
    return await get_response(prompt)

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


def structured_distillation_summary(raw_items: list[dict], char_limit: int = 1500) -> str:
    """Generate a hierarchical distilled summary for a set of memory originals.

    raw_items: list of {title, value}
    Returns markdown-like structured summary with sections:
      - Categories (inferred heuristically: preferences, biographical, meta, other)
      - Bullet points per item (compressed)
    Falls back to simple summarization if providers unavailable.
    """
    # Preprocess into heuristic buckets
    buckets = {"preferences": [], "biographical": [], "meta": [], "other": []}
    for it in raw_items:
        title = (it.get("title") or "").lower()
        val = (it.get("value") or "").strip()
        text = f"{title} {val}".lower()
        if any(k in text for k in ["favorite", "likes", "prefers", "dislikes", "enjoys"]):
            buckets["preferences"].append(it)
        elif any(k in text for k in ["age", "birthday", "born", "live", "location", "from", "work", "job", "profession"]):
            buckets["biographical"].append(it)
        elif any(k in text for k in ["recent", "session", "conversation", "chat", "note"]):
            buckets["meta"].append(it)
        else:
            buckets["other"].append(it)

    # Build a compressed raw representation to feed to model
    def _compress(items: list[dict], limit_each: int = 140):
        out = []
        for i in items:
            t = i.get("title") or "(untitled)"
            v = (i.get("value") or "").replace("\n", " ")
            if len(v) > limit_each:
                v = v[:limit_each-3] + "..."
            out.append(f"- {t}: {v}")
        return "\n".join(out)

    raw_compiled_sections = []
    for cat, items in buckets.items():
        if not items:
            continue
        raw_compiled_sections.append(f"[{cat}]\n{_compress(items)}")
    raw_compiled = "\n\n".join(raw_compiled_sections)
    if len(raw_compiled) > 6000:
        raw_compiled = raw_compiled[:6000]  # hard safety cap

    prompt = (
        "You are an AI system creating a distilled hierarchical memory summary.\n"
        "Input items are already grouped by loose category tags in square brackets.\n"
        "Produce a concise structured summary using markdown-like headings and bullets.\n"
        "Guidelines:\n"
        "- Keep total output under " + str(char_limit) + " characters.\n"
        "- Use top-level headings for each category present.\n"
        "- Rephrase to be terse, factual, and merge duplicates.\n"
        "- Omit trivial or redundant details.\n"
        "- If a category has no meaningful items, skip it.\n"
        "- End with a short 'Core Signals:' bullet list (≤5 items) summarizing the most impactful points.\n"
        "\nINPUT:\n" + raw_compiled + "\n\nSTRUCTURED SUMMARY:\n"
    )
    for idx, provider in enumerate(AI_PROVIDERS):
        if not _is_provider_available(provider):
            continue
        try:
            timeout_budget = settings.AI_PRIMARY_TIMEOUT if idx == 0 else settings.AI_FALLBACK_TIMEOUT
            def invoke() -> str:
                if provider == "gemini":
                    return _try_gemini(prompt)
                if provider == "anthropic":
                    return _try_anthropic(prompt)
                if provider == "cohere":
                    return _try_cohere(prompt)
                raise RuntimeError("Unknown provider")
            out = _call_with_timeout(invoke, timeout_budget)
            if len(out) > char_limit:
                out = out[:char_limit-3] + "..."
            return out
        except TimeoutError as te:
            logger.warning(f"[AI] Distillation structured summary provider '{provider}' timeout: {te}")
            FAILED_PROVIDERS[provider] = time.time()
        except Exception as e:
            logger.error(f"[AI] Structured distillation failed with '{provider}': {e}")
            FAILED_PROVIDERS[provider] = time.time()
    # Fallback: simple summarization of concatenated text
    fallback_text = "\n".join(f"{i.get('title')}: {i.get('value')}" for i in raw_items)[:char_limit]
    return summarize_text(fallback_text)

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
