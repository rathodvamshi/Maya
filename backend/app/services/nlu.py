# Complete, production-ready universal NLU + router
# Drop this into your services layer (replaces previous nlu.py).
# Assumes `app.services.ai_service` and `app.services.spacy_nlu` exist and work as before.

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
import pytz
import dateparser
import jsonschema
import hashlib
import httpx

from app.services import ai_service, spacy_nlu
from app.services import redis_service
from app.config import settings

logger = logging.getLogger(__name__)

# -----------------------
# Intent taxonomy (centralized)
# -----------------------
INTENT_TAXONOMY = [
    "create_task",
    "update_task",
    "delete_task",
    "complete_task",
    "fetch_tasks",
    "task_status",
    "chat_general",
    "qa_knowledge",
    "search_web",
    "calculator",
    "translate",
    "code_help",
    "book_flight",
    "hotel_search",
    "small_talk",
    "fallback",
]

# -----------------------
# JSON schemas (strict validation)
# -----------------------
INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "confidence": {"type": "number"},
        "top_k": {
            "type": "array",
            "items": {"type": "object", "properties": {"intent": {"type": "string"}, "score": {"type": "number"}}}
        }
    },
    "required": ["intent", "confidence"]
}

SLOT_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "datetime_iso": {"type": ["string", "null"]},
        "datetime_text": {"type": ["string", "null"]},
        "notes": {"type": ["string", "null"]},
        "repeat": {"type": ["string", "null"], "enum": [None, "daily", "weekly", "monthly"]},
        "channel": {"type": ["string", "null"], "enum": [None, "email", "chat", "both"]},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["title", "datetime_iso", "datetime_text", "missing_fields", "confidence"]
}

SLOT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": SLOT_TASK_SCHEMA,
            "minItems": 1
        }
    },
    "required": ["tasks"]
}

# Generic slot schema for non-task intents (simple permissive schema)
GENERIC_SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "slots": {"type": "object"},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"}
    },
    "required": ["confidence"]
}

# -----------------------
# Utilities
# -----------------------
def safe_json_embed(s: str) -> str:
    """Safely produce JSON-escaped string for embedding inside prompts."""
    return json.dumps(s, ensure_ascii=False)

def try_parse_time(time_text: Optional[str], user_timezone: str = "UTC") -> Optional[str]:
    """Server-side robust parsing to ISO UTC using dateparser (prefer future)."""
    if not time_text:
        return None
    try:
        settings = {
            "TIMEZONE": user_timezone or "UTC",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now(pytz.timezone(user_timezone or "UTC"))
        }
        dt = dateparser.parse(time_text, settings=settings)
        if dt:
            return dt.astimezone(pytz.UTC).isoformat()
    except Exception as e:
        logger.debug("dateparser parse error for %r: %s", time_text, e)
    return None

def normalize_channel(ch: Optional[str]) -> str:
    if not ch:
        return "email"
    ch = str(ch).lower().strip()
    if ch in ("email", "mail"):
        return "email"
    if ch in ("chat", "message", "in-app", "inapp"):
        return "chat"
    if ch in ("both",):
        return "both"
    return "email"

def validate_schema(obj: Any, schema: dict) -> Tuple[bool, Optional[str]]:
    try:
        jsonschema.validate(instance=obj, schema=schema)
        return True, None
    except Exception as e:
        return False, str(e)

# -----------------------
# Few-shot anchor examples (for task slot prompt)
# -----------------------
SLOT_FEWSHOT = [
    {
        "user_message": "Remind me to call mom in 1 minute",
        "user_timezone": "Asia/Kolkata",
        "tasks": [
            {
                "title": "call mom",
                "datetime_iso": None,
                "datetime_text": "in 1 minute",
                "notes": None,
                "repeat": None,
                "channel": "email",
                "missing_fields": [],
                "confidence": 0.98
            }
        ]
    },
    {
        "user_message": "Pay rent next Monday at 9am and schedule garbage pickup tomorrow evening",
        "user_timezone": "Asia/Kolkata",
        "tasks": [
            {
                "title": "pay rent",
                "datetime_iso": None,
                "datetime_text": "next Monday at 9am",
                "notes": None,
                "repeat": "monthly",
                "channel": "email",
                "missing_fields": [],
                "confidence": 0.95
            },
            {
                "title": "garbage pickup",
                "datetime_iso": None,
                "datetime_text": "tomorrow evening",
                "notes": None,
                "repeat": None,
                "channel": "email",
                "missing_fields": ["datetime"],
                "confidence": 0.85
            }
        ]
    },
    {
        "user_message": "Also, remind me tomorrow",
        "user_timezone": "Asia/Kolkata",
        "tasks": [
            {
                "title": None,
                "datetime_iso": None,
                "datetime_text": "tomorrow",
                "notes": None,
                "repeat": None,
                "channel": "email",
                "missing_fields": ["title", "datetime"],
                "confidence": 0.6
            }
        ]
    }
]

# -----------------------
# LLM call wrapper with retries + strict validation
# -----------------------
async def retry_llm_call(prompt: str, schema: dict, retries: int = 2, delay_s: float = 0.3) -> Optional[dict]:
    """
    Call the LLM and validate its JSON output against schema.
    If parsing/validation fails, retry with added instruction to only return JSON.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            # generate_ai_response is expected to be an async function returning a string
            resp = await ai_service.generate_ai_response(prompt)
            if not isinstance(resp, str) or not resp.strip():
                last_err = "Empty response"
                raise ValueError("Empty response")

            cleaned = resp.strip()
            # Robust extract of first valid JSON object in text (ignores emojis/markdown)
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                json_str = cleaned[start:end + 1]
            else:
                json_str = cleaned.replace("```json", "").replace("```", "").strip()
            try:
                obj = json.loads(json_str)
            except Exception as e:
                last_err = f"JSON parse error: {e}; raw: {cleaned[:400]}"
                raise

            ok, err = validate_schema(obj, schema)
            if not ok:
                last_err = f"Schema validation failed: {err}"
                raise ValueError(last_err)

            return obj
        except Exception as exc:
            logger.debug("LLM parse attempt %d failed: %s", attempt + 1, exc)
            # tighten instructions for next attempt
            prompt = (
                "IMPORTANT: Return only valid JSON that exactly matches the requested schema. "
                "Do not include any additional commentary or markdown. If you cannot determine a value, use null or an empty array as appropriate.\n\n"
                + prompt
            )
            time.sleep(delay_s * (attempt + 1))
    logger.warning("LLM retries exhausted: %s", last_err)
    return None

# -----------------------
# Fast heuristic path (improved)
# -----------------------
def _fast_path(user_message: str, user_timezone: str = "UTC") -> Dict[str, Any]:
    """
    Fast deterministic heuristics + spaCy fallback. Return {action, data, confidence, _fast}.
    This should be conservative and quick so we avoid LLM calls when possible.
    """
    lower = (user_message or "").lower().strip()
    spacy_res = {}
    try:
        spacy_res = spacy_nlu.extract(user_message) or {}
    except Exception:
        spacy_res = {}

    # Intent quick checks
    if any(kw in lower for kw in ["cancel my", "delete my", "remove my", "cancel reminder", "delete reminder"]):
        return {"action": "delete_task", "confidence": 0.9, "_fast": True}
    if any(kw in lower for kw in ["mark done", "mark as done", "complete", "i did", "i've done"]):
        return {"action": "complete_task", "confidence": 0.85, "_fast": True}
    if any(kw in lower for kw in ["reschedule", "update", "change time", "move reminder"]):
        return {"action": "update_task", "confidence": 0.85, "_fast": True}
    if any(kw in lower for kw in ["list tasks", "my tasks", "show tasks", "what are my tasks", "show my reminders"]):
        return {"action": "fetch_tasks", "confidence": 0.95, "_fast": True}
    if lower.startswith("my name is "):
        name = user_message.split(" ", 3)[-1].strip()
        return {"action": "save_fact", "data": {"key": "name", "value": name}, "confidence": 0.9, "_fast": True}
    if lower.startswith("i live in "):
        city = user_message.split(" ", 3)[-1].strip()
        return {"action": "save_fact", "data": {"key": "location", "value": city}, "confidence": 0.8, "_fast": True}

    # Math / calculator quick check
    if re.search(r"^\s*([-+*/^0-9().\s]{1,})\s*$", user_message) and any(ch in user_message for ch in "0123456789"):
        return {"action": "calculator", "data": {"expression": user_message.strip()}, "confidence": 0.9, "_fast": True}

    # Quick pattern: "in N minutes/hours/days" -> parse immediately
    m_rel = re.search(r"\bin\s+(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?)\b", lower)
    if m_rel:
        time_phrase = m_rel.group(0)
        parsed = try_parse_time(time_phrase, user_timezone)
        # naive title = message minus time phrase
        title_guess = re.sub(re.escape(time_phrase), "", lower).strip(" ,.")
        title_guess = title_guess if title_guess else user_message.strip()
        data = {"title": title_guess[:200], "datetime": parsed or time_phrase, "channel": None}
        confidence = 0.9 if parsed else 0.8
        return {"action": "create_task", "data": data, "confidence": confidence, "_fast": True}

    # Implicit verb detection (call, email, pay, etc.) suggests create_task
    implicit_verbs = r"\b(call|email|pay|meet|send|submit|book|attend|remember|check|open|start)\b"
    if re.search(implicit_verbs, lower):
        title = user_message.strip()
        return {"action": "create_task", "data": {"title": title[:200], "datetime": None}, "confidence": 0.7, "_fast": True}

    # Fallback: general chat
    return {"action": "general_chat", "confidence": 0.5, "_fast": True}

# -----------------------
# Public entrypoint: universal intent + slot extraction + normalization
# -----------------------
async def get_structured_intent(user_message: str, user_timezone: Optional[str] = None) -> dict:
    """
    Universal NLU entrypoint.
    Returns a dict: {"action": <intent_action>, "data": <payload>}
    For create_task: data will be either a single task dict or {"tasks": [ ... ]}.
    For other intents: data contains relevant slots or minimal information.
    """
    tz = user_timezone or "UTC"
    fast = _fast_path(user_message, tz)

    # If fast path confident and not create_task (or already fully resolved create_task), return quickly
    if fast.get("action") != "create_task" and fast.get("confidence", 0) >= 0.8:
        result = {"action": fast.get("action")}
        if "data" in fast:
            result["data"] = fast["data"]
        return result

    if fast.get("action") == "create_task" and fast.get("confidence", 0) >= 0.9 and fast.get("data", {}).get("datetime"):
        # ensure channel normalized
        fast["data"]["channel"] = normalize_channel(fast["data"].get("channel"))
        return {"action": "create_task", "data": fast["data"]}

    # Otherwise run intent classifier LLM (lightweight)
    intent_prompt = (
        "You are an intent classifier. Return ONLY valid JSON matching this schema: "
        "{\"intent\": \"create_task\" | \"none\" | \"ambiguous\", \"confidence\": 0.0}.\n\n"
        f"Input: {{'user_message': {safe_json_embed(user_message)}, 'user_timezone': '{tz}'}}\n"
        "Rules: Choose create_task when the user asks to schedule, remember, set or implies a future action (e.g., 'call mom in 1 min', 'pay rent next month'). "
        "If unsure, return 'ambiguous'. Use a deterministic approach (do not be verbose)."
    )

    intent_obj = await retry_llm_call(intent_prompt, {"type": "object", "properties": {"intent": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["intent", "confidence"]}, retries=1)
    intent_val = None
    intent_conf = 0.0
    if intent_obj:
        intent_val = intent_obj.get("intent")
        intent_conf = float(intent_obj.get("confidence") or 0.0)
    else:
        intent_val = fast.get("action") or "general_chat"
        intent_conf = float(fast.get("confidence", 0.5))

    # Map non-create intents to actions (fallback to fast path)
    if intent_val != "create_task":
        if fast.get("action") and fast.get("action") != "create_task":
            return {"action": fast.get("action"), "data": fast.get("data", None)}
        # otherwise general chat or other intents will be handled by skill router upstream
        return {"action": "general_chat"}

    # Slot extraction for tasks (allow multiple tasks)
    slot_prompt = (
        "You are a task slot extractor. Return ONLY JSON matching this schema: {\"tasks\": [ {title, datetime_iso, datetime_text, notes, repeat, channel, missing_fields, confidence} ] }.\n"
        "Include both datetime_iso (resolved ISO string if possible) and datetime_text (original phrase). "
        "If you cannot resolve to ISO, set datetime_iso=null and include 'datetime' in missing_fields.\n"
        f"Few-shot examples (do not output them as part of result): {json.dumps(SLOT_FEWSHOT, ensure_ascii=False)}\n\n"
        f"Input: {{'user_message': {safe_json_embed(user_message)}, 'user_timezone': '{tz}'}}\n"
    )

    llm_json = await retry_llm_call(slot_prompt, SLOT_RESPONSE_SCHEMA, retries=2, delay_s=0.5)
    tasks_normalized: List[Dict[str, Any]] = []

    if llm_json and isinstance(llm_json, dict):
        tasks_raw = llm_json.get("tasks") or []
        for raw in tasks_raw:
            ok, err = validate_schema(raw, SLOT_TASK_SCHEMA)
            if not ok:
                logger.debug("Per-task schema failed: %s, raw=%r", err, raw)
                # attempt best-effort normalization
            title = raw.get("title") if isinstance(raw.get("title"), str) else None
            dt_iso = raw.get("datetime_iso") if isinstance(raw.get("datetime_iso"), str) else None
            dt_text = raw.get("datetime_text") if isinstance(raw.get("datetime_text"), str) else None
            notes = raw.get("notes") if isinstance(raw.get("notes"), str) else None
            repeat = raw.get("repeat") if isinstance(raw.get("repeat"), str) else None
            channel = normalize_channel(raw.get("channel"))
            missing = raw.get("missing_fields") if isinstance(raw.get("missing_fields"), list) else []
            conf = float(raw.get("confidence") or 0.0)

            # server-side enrichment if ISO missing
            if not dt_iso and dt_text:
                parsed = try_parse_time(dt_text, tz)
                if parsed:
                    dt_iso = parsed
                    missing = [m for m in missing if m != "datetime"]

            tasks_normalized.append({
                "title": title[:200] if title else None,
                "datetime": dt_iso,
                "datetime_text": dt_text if dt_text and dt_text != dt_iso else None,
                "notes": notes,
                "repeat": repeat,
                "channel": channel,
                "missing_fields": missing,
                "confidence": conf,
                "user_timezone": tz,
                "ts": datetime.now(pytz.timezone(tz)).strftime('%Y-%m-%d %H:%M:%S %Z'),
            })

    # If LLM returned nothing useful, fallback to fast path attempt
    if not tasks_normalized:
        fast_data = fast.get("data", {})
        dt_raw = fast_data.get("datetime")
        dt_iso = None
        if dt_raw:
            # attempt to parse
            dt_iso = try_parse_time(str(dt_raw), tz)
        tasks_normalized = [{
            "title": fast_data.get("title")[:200] if fast_data.get("title") else None,
            "datetime": dt_iso,
            "datetime_text": None if dt_iso else (dt_raw or None),
            "notes": None,
            "repeat": None,
            "channel": normalize_channel(fast_data.get("channel")),
            "missing_fields": [] if dt_iso else ["datetime"],
            "confidence": float(fast.get("confidence", 0.5)),
            "user_timezone": tz,
            "ts": datetime.now(pytz.timezone(tz)).strftime('%Y-%m-%d %H:%M:%S %Z'),
        }]

    # Return single item for backward compatibility when only one task
    if len(tasks_normalized) == 1:
        return {"action": "create_task", "data": tasks_normalized[0]}
    return {"action": "create_task", "data": {"tasks": tasks_normalized}}

# -----------------------
# Example convenience router (small utility)
# -----------------------
def route_intent_to_skill(nlu_result: dict) -> dict:
    """
    Simple router convenience function returning a canonical routing result.
    Not strictly required, but useful for integrating into the session manager.
    """
    action = nlu_result.get("action")
    data = nlu_result.get("data")
    # Map synonyms or fallback
    if action in ("create_task", "update_task", "delete_task", "complete_task", "fetch_tasks"):
        return {"skill": "tasks", "intent": action, "payload": data}
    if action == "calculator":
        return {"skill": "calculator", "intent": action, "payload": data}
    if action == "general_chat":
        return {"skill": "chat", "intent": "chat_general", "payload": data}
    # default fallback
    return {"skill": "chat", "intent": action or "fallback", "payload": data}

# -----------------------
# Gemini-based NLU (async, strict JSON schema)
# -----------------------

SYSTEM_PROMPT = (
    "\n".join([
        "You are an intelligent Natural Language Understanding (NLU) engine.",
        "",
        "Your task:",
        "",
        "Identify the user's intent.",
        "",
        "Extract entities relevant to that intent.",
        "",
        "If the input is ambiguous or incomplete:",
        "",
        "Do NOT guess.",
        "",
        "Ask a short, friendly clarification question.",
        "",
        "Output strictly JSON.",
        "",
        "Schema:",
        "{",
        "\"intent\": string | null,",
        "\"entities\": object | null,",
        "\"clarification_needed\": boolean,",
        "\"question\": string | null",
        "}",
        "",
        "Rules:",
        "",
        "Set clarification_needed=true and provide a question if needed.",
        "",
        "Set clarification_needed=false if confident and fill intent/entities.",
        "",
        "Always return valid JSON; do not include natural language outside JSON.",
    ])
)

def _gemini_model_name() -> str:
    # Prefer the requested 2.5-flash if configured; fallback to existing setting or a sane default
    return getattr(settings, "GOOGLE_MODEL", None) or "gemini-1.5-flash"

def _gemini_endpoint() -> str:
    model = _gemini_model_name()
    # Google Generative Language API v1beta endpoint for generateContent
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

def _gemini_headers() -> Dict[str, str]:
    api_key = (getattr(settings, "GEMINI_API_KEY", None) or "").strip()
    # Prefer GEMINI_API_KEYS (comma-separated); pick first if present
    keys = [k.strip() for k in (getattr(settings, "GEMINI_API_KEYS", None) or "").split(",") if k.strip()]
    if keys:
        api_key = keys[0]
    return {"Content-Type": "application/json", "x-goog-api-key": api_key}

def _build_prompt(user_message: str, clarification_answers: Optional[List[str]] = None) -> str:
    if clarification_answers:
        clar = "\n".join([f"User clarification: {c}" for c in clarification_answers if c])
        return f"{SYSTEM_PROMPT}\n\nUser message: {user_message}\n{clar}"
    return f"{SYSTEM_PROMPT}\n\nUser message: {user_message}"

def _cache_key(user_id: Optional[str], session_id: Optional[str], message: str) -> str:
    raw = f"{user_id or ''}|{session_id or ''}|{message}"
    return "nlu:gemini:v1:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _normalize_output(obj: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure all required keys exist with proper types
    intent = obj.get("intent") if isinstance(obj.get("intent"), str) else None
    entities = obj.get("entities") if isinstance(obj.get("entities"), dict) else ({} if obj.get("entities") else None)
    clarification_needed = bool(obj.get("clarification_needed"))
    question = obj.get("question") if isinstance(obj.get("question"), str) else None
    if clarification_needed and not question:
        question = "Could you clarify your request?"
    return {
        "intent": intent,
        "entities": entities,
        "clarification_needed": clarification_needed,
        "question": question,
    }

async def _call_gemini_json(user_message: str, clarification_answers: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Call Gemini asynchronously and attempt to parse a strict-JSON reply."""
    endpoint = _gemini_endpoint()
    headers = _gemini_headers()
    payload = {
        # Minimal request with a single content; system-style prompt prepended to user message
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _build_prompt(user_message, clarification_answers)}],
            }
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500},
    }
    # Attach API key via query string per Google API; retain header for flexibility
    api_key = headers.get("x-goog-api-key", "")
    params = {"key": api_key} if api_key else {}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(endpoint, headers={"Content-Type": "application/json"}, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Gemini JSON parsing (extract text from candidates[0].content.parts)
            text = None
            try:
                candidates = data.get("candidates") or []
                if candidates:
                    parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
                    if parts and isinstance(parts[0], dict):
                        text = parts[0].get("text")
            except Exception:
                text = None
            if not text:
                return None
            # Robustly strip to first JSON object
            s = text.strip()
            start = s.find("{")
            end = s.rfind("}")
            json_str = s[start:end + 1] if (start != -1 and end != -1 and end > start) else s
            obj = json.loads(json_str)
            return _normalize_output(obj)
    except Exception as e:
        logger.warning("Gemini call failed: %s", e)
        return None

async def extract_intent_entities(
    *,
    message: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    max_clarifications: int = 2,
    clarification_answers: Optional[List[str]] = None,
    cache_ttl_seconds: int = 300,
) -> Dict[str, Any]:
    """
    Async NLU entrypoint for the chat router (Step 2 integration).
    - Normalizes inputs
    - Uses Redis for short-term caching
    - Calls Gemini asynchronously for strict JSON output
    - Supports a bounded clarification loop (callers provide clarification_answers in subsequent calls)
    Returns dict with keys: intent, entities, clarification_needed, question.
    """
    user_message = (message or "").strip()
    if not user_message:
        return {
            "intent": None,
            "entities": None,
            "clarification_needed": True,
            "question": "Please share your request so I can help.",
        }

    # Attempt cache lookup (only for initial query without clarifications)
    cached: Optional[Dict[str, Any]] = None
    try:
        if not clarification_answers:
            client = redis_service.get_client()
            if client:
                key = _cache_key(user_id, session_id, user_message)
                cached = await client.get(key)
                if cached:
                    try:
                        cached_obj = json.loads(cached)
                        return _normalize_output(cached_obj)
                    except Exception:
                        cached = None
    except Exception:
        cached = None

    # Clarification loop (external interaction is handled by caller; we just compute question)
    answers: List[str] = list(clarification_answers or [])
    attempt = 0
    result: Optional[Dict[str, Any]] = None
    while attempt <= max_clarifications:
        result = await _call_gemini_json(user_message, answers if answers else None)
        if not result:
            # graceful fallback
            return {
                "intent": None,
                "entities": None,
                "clarification_needed": True,
                "question": "I ran into an issue analyzing that. Could you rephrase or add details?",
            }
        if not result.get("clarification_needed"):
            break
        # If clarification is still needed and we already consumed provided answers, break
        if attempt >= max_clarifications or (clarification_answers and attempt >= len(answers)):
            break
        attempt += 1

    # Cache only confident final results (no clarification needed)
    try:
        if result and not result.get("clarification_needed"):
            client = redis_service.get_client()
            if client:
                key = _cache_key(user_id, session_id, user_message)
                await client.setex(key, cache_ttl_seconds, json.dumps(result))
    except Exception:
        pass

    # Ensure normalized output
    return _normalize_output(result or {})