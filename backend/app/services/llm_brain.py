# backend/app/services/llm_brain.py

"""
LLM Brain Layer (Step 3)

Responsibilities:
- Gather relevant short-term and long-term memories in parallel (Redis, Pinecone, Neo4j)
- Select among multiple Gemini 2.5-flash APIs with usage/limits and fallback
- Produce a structured JSON plan for the NLG layer and downstream actions
- Run non-critical updates/logging asynchronously to avoid blocking

Notes:
- This module is additive and does not replace existing flows; callers can opt-in.
- All functions are async and safe to call from FastAPI endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio
import logging
import json
from datetime import datetime

from fastapi.concurrency import run_in_threadpool

from app.services import redis_service
from app.services import pinecone_service
from app.services.neo4j_service import neo4j_service
from app.database import db_client

logger = logging.getLogger(__name__)


# -----------------------------------------------------
# Gemini API pool with simple usage accounting + selection
# -----------------------------------------------------

# In-memory counters (optionally persisted by the host app at startup/shutdown)
gemini_apis: Dict[str, Dict[str, Any]] = {
    # Example: tune limits per deployment; these are soft counters
    "api_nlu": {"type": "NLU", "limit": 1000, "used": 0, "active": True},
    "api_embed": {"type": "Embeddings", "limit": 5000, "used": 0, "active": True},
    "api_text": {"type": "TextCompletion", "limit": 2000, "used": 0, "active": True},
}


def check_api_limits() -> None:
    for api in gemini_apis.values():
        api["active"] = api.get("used", 0) < api.get("limit", 0)


def select_gemini_api(required_type: str) -> Optional[str]:
    """Select the first active API matching the required type."""
    check_api_limits()
    for api_name, api in gemini_apis.items():
        if api.get("type") == required_type and api.get("active"):
            return api_name
    return None


def use_api(api_name: str) -> None:
    api = gemini_apis.get(api_name)
    if not api:
        return
    api["used"] = int(api.get("used", 0)) + 1
    if api["used"] >= api.get("limit", 0):
        api["active"] = False


# -----------------------------------------------------
# Memory fetching helpers (async, parallel)
# -----------------------------------------------------

@dataclass
class MemorySnippet:
    source: str  # "redis" | "pinecone" | "neo4j"
    id: str
    snippet: str
    confidence: float  # 0.0 - 1.0


async def _fetch_redis_context(user_id: str, session_id: str) -> List[MemorySnippet]:
    """Fetch short-term context/history from Redis. Best-effort and non-fatal."""
    out: List[MemorySnippet] = []
    try:
        client = redis_service.get_client()
        if not client:
            return out
        # Session state
        try:
            state_key = f"session:state:{session_id}"
            state = await client.get(state_key)
            if state:
                out.append(MemorySnippet(source="redis", id=state_key, snippet=state, confidence=0.7))
        except Exception:
            pass
        # Recent messages list (if present)
        try:
            msgs_key = f"sess:{session_id}:msgs"
            # Return last ~10 messages (compact JSON strings)
            items = await client.lrange(msgs_key, -10, -1)
            if items:
                joined = "\n".join(items[:10])
                out.append(MemorySnippet(source="redis", id=msgs_key, snippet=joined, confidence=0.65))
        except Exception:
            pass
    except Exception:
        pass
    return out


async def _fetch_pinecone_memories(user_id: str, hint_text: str, top_k: int = 5) -> List[MemorySnippet]:
    """Query Pinecone for user memories and similar texts. Runs in threadpool (SDK is sync)."""
    def _query() -> List[MemorySnippet]:
        snippets: List[MemorySnippet] = []
        try:
            # Top memory vectors for this user
            vecs = pinecone_service.query_user_memories(user_id, hint_text, top_k=top_k) or []
            for v in vecs:
                text = v.get("text") or ""
                sim = float(v.get("similarity") or 0.0)
                snippets.append(MemorySnippet(source="pinecone", id=str(v.get("memory_id") or ""), snippet=text, confidence=max(0.0, min(sim, 1.0))))
            # Similar prior message context
            try:
                joined = pinecone_service.query_similar_texts(user_id, hint_text, top_k=top_k) or ""
                if joined:
                    snippets.append(MemorySnippet(source="pinecone", id="similar_texts", snippet=joined, confidence=0.6))
            except Exception:
                pass
        except Exception:
            pass
        return snippets

    return await run_in_threadpool(_query)


async def _fetch_neo4j_semantic(user_id: str) -> List[MemorySnippet]:
    """Fetch relationship facts from Neo4j Aura (async driver)."""
    out: List[MemorySnippet] = []
    try:
        facts = await neo4j_service.get_user_facts(user_id)
        if facts:
            # Store as a single snippet to avoid excess payload
            out.append(MemorySnippet(source="neo4j", id="facts", snippet=facts, confidence=0.7))
    except Exception:
        pass
    return out


async def gather_memories(user_id: str, session_id: str, hint_text: str) -> List[MemorySnippet]:
    """Fetch Redis, Pinecone, and Neo4j memories concurrently."""
    tasks = [
        asyncio.create_task(_fetch_redis_context(user_id, session_id)),
        asyncio.create_task(_fetch_pinecone_memories(user_id, hint_text, top_k=5)),
        asyncio.create_task(_fetch_neo4j_semantic(user_id)),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: List[MemorySnippet] = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
    return merged


# -----------------------------------------------------
# Planning / Decision logic
# -----------------------------------------------------

def _required_fields_for_intent(intent: Optional[str]) -> List[str]:
    if not intent:
        return []
    # Minimal examples; extend per domain
    if intent in ("create_task", "book_flight", "book_train_ticket", "book_hotel"):
        return ["title" if intent == "create_task" else "destination"]
    return []


def _compute_missing_fields(intent: Optional[str], entities: Dict[str, Any]) -> List[str]:
    required = _required_fields_for_intent(intent)
    missing: List[str] = []
    for f in required:
        if not entities or entities.get(f) in (None, ""):
            missing.append(f)
    return missing


def _normalize_entities(entities: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Wrap entity values with source/confidence placeholders; sources will be augmented from memories."""
    out: Dict[str, Dict[str, Any]] = {}
    base = entities or {}
    for k, v in base.items():
        out[k] = {"value": v, "source": ["user"], "confidence": 0.9}
    return out


def _augment_entities_with_memories(entities_wrapped: Dict[str, Dict[str, Any]], memories: List[MemorySnippet]) -> None:
    """Heuristic augmentation: if a snippet obviously contains an entity value, attribute source and boost confidence."""
    for m in memories:
        for k, meta in list(entities_wrapped.items()):
            try:
                val = str(meta.get("value", ""))
                if val and val.lower() in (m.snippet or "").lower():
                    srcs = list(meta.get("source", []))
                    if m.source not in srcs:
                        srcs.append(m.source)
                    # soft cap confidence
                    meta["confidence"] = min(1.0, float(meta.get("confidence", 0.7)) + 0.1)
                    meta["source"] = srcs
            except Exception:
                continue


async def plan_actions(
    *,
    intent: Optional[str],
    entities: Optional[Dict[str, Any]],
    user_id: str,
    session_id: str,
    required_function: str = "TextCompletion",  # "NLU" | "Embeddings" | "TextCompletion"
    hint_text: str = "",
) -> Dict[str, Any]:
    """
    Central brain entrypoint. Produces a structured JSON plan suitable for the NLG layer.
    """
    # Fetch memories in parallel (non-blocking with each other)
    memories = await gather_memories(user_id=user_id, session_id=session_id, hint_text=hint_text)

    # Select provider
    provider_id = select_gemini_api(required_function)
    if not provider_id:
        # No matching active provider; graceful fallback
        plan = {
            "actions": [
                {"action": "fallback", "parameters": {"reason": f"No active provider for {required_function}"}, "execute_now": False}
            ]
        }
        return {
            "intent": intent,
            "entities": _normalize_entities(entities),
            "missing_required_fields": _compute_missing_fields(intent, entities or {}),
            "ambiguities": [],
            "gathered_memory": [m.__dict__ for m in memories],
            "external_calls_needed": [],
            "plan": plan,
            "api_provider_used": {"provider_id": None, "checked_limit": True},
            "log": {"warnings": [f"No active provider for {required_function}"], "errors": []},
            "confidence": 0.6,
        }

    # Mark usage (non-blocking update in background to avoid delaying return)
    try:
        use_api(provider_id)
    except Exception:
        pass

    # Normalize and augment entities using memories
    entities_wrapped = _normalize_entities(entities)
    _augment_entities_with_memories(entities_wrapped, memories)

    # Decide on external calls needed
    external_calls_needed: List[Dict[str, Any]] = []
    if intent in ("book_flight", "book_train_ticket", "book_hotel"):
        external_calls_needed.append({"type": "gemini_text", "reason": "Generate booking steps", "required": True})

    # Compose a minimal plan; execution is performed by downstream layers/services
    actions: List[Dict[str, Any]] = []
    if intent == "create_task":
        actions.append({
            "action": "create_task",
            "parameters": {"entities": entities_wrapped},
            "execute_now": True,
        })
    elif intent in ("book_flight", "book_train_ticket", "book_hotel"):
        actions.append({
            "action": "call_api",
            "parameters": {"provider": provider_id, "reason": "booking flow"},
            "execute_now": False,
        })
    else:
        actions.append({
            "action": "general_response",
            "parameters": {"provider": provider_id},
            "execute_now": False,
        })

    # Background: persist provider usage / telemetry if needed
    async def _telemetry():
        try:
            logger.info("[LLM_BRAIN] provider=%s used at %s", provider_id, datetime.utcnow().isoformat())
        except Exception:
            pass

    # Background: task management orchestration when intent implies tasking
    async def _task_side_effects():
        try:
            if intent == "create_task":
                # Minimal shape: title/due_date in entities if present
                title = None
                due = None
                e = entities or {}
                # Prefer structured value if wrapped form is passed accidentally
                if isinstance(e.get("title"), dict):
                    title = e["title"].get("value")
                else:
                    title = e.get("title")
                if isinstance(e.get("due_date"), dict):
                    due = e["due_date"].get("value")
                else:
                    due = e.get("due_date") or e.get("datetime")

                tasks_col = db_client.get_tasks_collection()
                if tasks_col:
                    doc = {
                        "user_id": user_id,
                        "session_id": session_id,
                        "title": title or (hint_text[:80] if hint_text else "Task"),
                        "run_at": due,
                        "payload": {"entities": entities or {}},
                        "status": "pending",
                        "created_at": datetime.utcnow(),
                    }
                    await run_in_threadpool(tasks_col.insert_one, doc)
        except Exception:
            try:
                logger.debug("LLM_BRAIN task_side_effects failed", exc_info=True)
            except Exception:
                pass

    try:
        asyncio.create_task(_telemetry())
        asyncio.create_task(_task_side_effects())
    except Exception:
        pass

    # Structured, strict-JSON for NLG including memory updates skeleton
    return {
        "nlg_input": {
            "intent": intent,
            "entities": entities_wrapped,
            "gathered_memory": [m.__dict__ for m in memories],
            "external_calls_needed": external_calls_needed,
            "plan": {"actions": actions},
            "api_provider_used": {"provider_id": provider_id, "checked_limit": True},
            "confidence": 0.8 if provider_id else 0.6,
        },
        "memory_updates": {
            "redis": {},
            "pinecone": {},
            "neo4j": {},
            "profile_db": {},
        },
        "tasks": actions if any(a.get("action") == "create_task" for a in actions) else [],
        "api_calls": external_calls_needed,
        "log": {"warnings": [], "errors": []},
    }


