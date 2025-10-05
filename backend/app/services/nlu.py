# backend/app/services/nlu.py

from app.services import ai_service
from app.services import spacy_nlu
import json
from datetime import datetime
from typing import Dict, Any


def _fast_path(user_message: str) -> Dict[str, Any]:
    """Cheap heuristic + spaCy pass to classify into one of our target actions.

    Returns a dict with keys:
      {"action": <str>, "data": {...optional...}, "confidence": float, "_fast": True}

    Confidence is a coarse heuristic (0..1). Caller decides fallback threshold.
    """
    lower = user_message.lower().strip()
    data: Dict[str, Any] = {}
    confidence = 0.4  # base

    # Task creation patterns
    task_triggers = ["remind me", "add task", "create task", "schedule", "todo", "to-do", "set a reminder"]
    if any(t in lower for t in task_triggers):
        # Attempt title extraction (naive)
        title = user_message
        for t in task_triggers:
            if t in lower:
                # crude slice after trigger
                idx = lower.find(t) + len(t)
                possible = user_message[idx:].strip(" :,-")
                if possible:
                    title = possible
                    break
        data = {"title": title[:120]}
        return {"action": "create_task", "data": data, "confidence": 0.85, "_fast": True}

    # Fetch tasks
    if any(p in lower for p in ["my tasks", "list tasks", "show tasks", "what are my tasks"]):
        return {"action": "fetch_tasks", "confidence": 0.9, "_fast": True}

    # Save fact (simple name / preference patterns)
    if lower.startswith("my name is "):
        name = user_message.split(" ", 3)[-1].strip()
        return {"action": "save_fact", "data": {"key": "name", "value": name}, "confidence": 0.9, "_fast": True}
    if lower.startswith("i live in "):
        city = user_message.split(" ", 3)[-1].strip()
        return {"action": "save_fact", "data": {"key": "location", "value": city}, "confidence": 0.8, "_fast": True}

    # Trip planning (reuse spaCy helper intent)
    extracted = spacy_nlu.extract(user_message)
    if extracted.get("intent") == "PLAN_TRIP" and extracted.get("entities", {}).get("destination"):
        return {"action": "create_task", "data": {"title": f"Plan trip to {extracted['entities']['destination']}"}, "confidence": 0.75, "_fast": True}

    # Fallback general_chat fast path result
    return {"action": "general_chat", "confidence": confidence, "_fast": True}

async def get_structured_intent(user_message: str) -> dict:
    """Hybrid NLU: fast deterministic path first, LLM fallback when low confidence or enrichment needed.

    Fallback triggers:
      - Fast path confidence < 0.7 for non-general actions
      - Need datetime normalization for create_task (no explicit datetime parsed)
      - Potential ambiguous patterns (general_chat with low confidence)
    """
    fast = _fast_path(user_message)

    # If we are highly confident OR it's a simple fetch/save_fact with adequate data, return early
    if fast["action"] in ("fetch_tasks", "save_fact") and fast.get("confidence", 0) >= 0.6:
        return {k: v for k, v in fast.items() if not k.startswith("_") and k != "confidence"}
    if fast["action"] == "create_task" and fast.get("confidence", 0) >= 0.8:
        # Still may need datetime enrichment: if user didn't supply relative time, we rely on LLM
        # Heuristic: if words like 'tomorrow', 'next', 'in ' appear -> require enrichment
        lower = user_message.lower()
        needs_time = any(w in lower for w in ["tomorrow", " next ", " in ", " tonight", " morning", " afternoon", " evening"]) and " at " not in lower
        if not needs_time:
            return {k: v for k, v in fast.items() if not k.startswith("_") and k != "confidence"}
    if fast["action"] == "general_chat" and fast.get("confidence", 0) >= 0.75:
        return {"action": "general_chat"}

    # Otherwise build prompt and call LLM to upgrade/normalize
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prompt = f"""
You are a precise NLU JSON engine. Current time: {current_time}
User message: {user_message}\n
Return ONLY JSON per one of schemas:
create_task: {{"action":"create_task","data":{{"title":"...","datetime":"YYYY-MM-DD HH:MM","priority":"high|medium|low","category":"work|personal|general","notes":"..."}}}}
fetch_tasks: {{"action":"fetch_tasks"}}
save_fact: {{"action":"save_fact","data":{{"key":"...","value":"..."}}}}
general_chat: {{"action":"general_chat"}}

Rules:
- Convert relative temporal phrases to absolute datetime using current time.
- If no time given for a create_task, infer a reasonable default (next 9am local) but still produce a datetime.
- Never include explanatory text—only JSON.
"""
    try:
        response_text = await ai_service.generate_ai_response(prompt)  # async alias
        if isinstance(response_text, str):
            cleaned = response_text.strip().replace('```json', '').replace('```', '').strip()
            result = json.loads(cleaned)
            if isinstance(result, dict) and result.get("action"):
                return result
    except Exception as e:  # noqa: BLE001
        print(f"NLU fallback LLM error: {e}")
    # Fallback final
    return {"action": fast.get("action", "general_chat")}
