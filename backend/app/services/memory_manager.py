# backend/app/services/memory_manager.py

"""
Unified Memory Manager (Step 5)

Centralizes async storage, recall, and synchronization across:
- Redis (short-term)
- Pinecone (long-term embeddings)
- Neo4j (semantic relationships)
- Profile DB (persistent facts & tasks)

Usage:
  await memory_manager.update_memories(memory_updates, user_id, session_id)
  recalled = await memory_manager.recall_context(user_id, session_id, query_text)

All operations run asynchronously and are designed to be called from a
non-blocking context (e.g., via asyncio.create_task from the LLM Brain).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import asyncio
import logging
import os
import hashlib
from datetime import datetime

from fastapi.concurrency import run_in_threadpool

from app.services import redis_service
from app.services import pinecone_service
from app.services.neo4j_service import neo4j_service
from app.database import db_client

logger = logging.getLogger(__name__)

DEBUG_MEMORY = os.getenv("DEBUG_MEMORY", "false").lower() == "true"


# -----------------------------
# Redis — Short-Term Context
# -----------------------------

async def store_short_term_context(session_id: str, message: str, ttl_seconds: int = 24 * 3600) -> bool:
    """Append a compact message entry to the short-term Redis history and update state snapshot.

    Keys:
      - sess:{session_id}:msgs  -> list of compact strings
      - state:session:{session_id} -> last message snapshot (compat)
      - session:state:{session_id} -> last message snapshot (existing compat)
    """
    client = redis_service.get_client()
    if not client:
        return False
    try:
        msg_key = f"sess:{session_id}:msgs"
        # Trim to last ~50 messages; we only need a light footprint
        await client.rpush(msg_key, message)
        await client.ltrim(msg_key, -50, -1)
        await client.expire(msg_key, ttl_seconds)

        snap = message[:400]
        # New spec key
        state_key = f"state:session:{session_id}"
        await client.set(state_key, snap, ex=ttl_seconds)
        # Back-compat with existing modules
        compat_key = f"session:state:{session_id}"
        await client.set(compat_key, snap, ex=ttl_seconds)
        return True
    except Exception:
        try:
            logger.debug("store_short_term_context failed", exc_info=True)
        except Exception:
            pass
        return False


async def fetch_recent_context(session_id: str, last_n: int = 10) -> Dict[str, Any]:
    """Fetch recent compact context from Redis."""
    out: Dict[str, Any] = {"messages": [], "state": None}
    client = redis_service.get_client()
    if not client:
        return out
    try:
        out["messages"] = await client.lrange(f"sess:{session_id}:msgs", -last_n, -1)
    except Exception:
        pass
    try:
        val = await client.get(f"state:session:{session_id}")
        out["state"] = val
        if not val:
            out["state"] = await client.get(f"session:state:{session_id}")
    except Exception:
        pass
    return out


# -----------------------------
# Pinecone — Long-Term Memory
# -----------------------------

def _hash_metadata(user_id: str, text: str, metadata: Optional[Dict[str, Any]]) -> str:
    base = json_safe_dumps({"uid": user_id, "text": text, "meta": metadata or {}})
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def json_safe_dumps(obj: Any) -> str:
    try:
        import json as _json
        return _json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(obj)


async def upsert_embedding(user_id: str, text: str, metadata: Optional[Dict[str, Any]] = None, lifecycle_state: str = "candidate") -> bool:
    """Upsert a long-term memory embedding. Deduplicate by metadata hash.

    We leverage existing pinecone_service upsert which computes embeddings internally.
    Runs via threadpool due to sync SDK.
    """
    try:
        mem_hash = _hash_metadata(user_id, text or "", metadata)
        memory_id = f"mem:{user_id}:{mem_hash}"
        await run_in_threadpool(pinecone_service.upsert_memory_embedding, memory_id, user_id, text or "", lifecycle_state)
        return True
    except Exception:
        try:
            logger.debug("upsert_embedding failed", exc_info=True)
        except Exception:
            pass
        return False


async def query_user_memories(user_id: str, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Query top-k user memories from Pinecone."""
    def _q() -> List[Dict[str, Any]]:
        try:
            return pinecone_service.query_user_memories(user_id, query_text, top_k) or []
        except Exception:
            return []
    return await run_in_threadpool(_q)


# -----------------------------
# Neo4j — Semantic Memory
# -----------------------------

async def merge_fact_relationship(user_id: str, entity_a: str, relation: str, entity_b: str, confidence: float = 0.8) -> bool:
    """Merge a relationship, using uppercase rel names and MERGE semantics inside service layer."""
    try:
        rel = relation or "RELATED_TO"
        # Prefer generic create_relation which MERGEs user and concept
        await neo4j_service.create_relation(user_id, rel, entity_b)
        # For a richer schema (entity_a -> relation -> entity_b), extend neo4j_service accordingly
        return True
    except Exception:
        try:
            logger.debug("merge_fact_relationship failed", exc_info=True)
        except Exception:
            pass
        return False


async def get_user_facts(user_id: str) -> str:
    try:
        return await neo4j_service.get_user_facts(user_id)
    except Exception:
        return ""


# -----------------------------
# Profile DB — Persistent Records
# -----------------------------

async def update_user_profile(user_id: str, changes: Dict[str, Any]) -> bool:
    col = db_client.get_user_profile_collection()
    if not col:
        return False
    try:
        # Only set changed fields (merge semantics)
        await run_in_threadpool(col.update_one, {"_id": str(user_id)}, {"$set": changes}, True)
        return True
    except Exception:
        try:
            logger.debug("update_user_profile failed", exc_info=True)
        except Exception:
            pass
        return False


async def add_completed_task(user_id: str, task_id: str, details: Dict[str, Any]) -> bool:
    tasks_col = db_client.get_tasks_collection()
    prof_col = db_client.get_user_profile_collection()
    ok = True
    try:
        if tasks_col:
            await run_in_threadpool(tasks_col.update_one, {"_id": details.get("_id") or task_id}, {"$set": {"status": "done", "completed_at": datetime.utcnow()}}, False)
    except Exception:
        ok = False
    try:
        if prof_col:
            await run_in_threadpool(prof_col.update_one, {"_id": str(user_id)}, {"$push": {"completed_tasks": {"$each": [details], "$slice": -100}}}, True)
    except Exception:
        ok = False
    return ok


# -----------------------------
# Unified Manager API
# -----------------------------

async def update_memories(memory_updates: Dict[str, Any], user_id: str, session_id: str) -> Dict[str, Any]:
    """Dispatch updates to Redis, Pinecone, Neo4j, and Profile DB in parallel.
    Swallow non-critical errors; return a compact telemetry object.
    """
    updates = memory_updates or {}
    redis_upd = updates.get("redis") or {}
    pine_upd = updates.get("pinecone") or {}
    neo4j_upd = updates.get("neo4j") or {}
    profile_upd = updates.get("profile_db") or {}

    tasks: List[asyncio.Task] = []

    # Redis session summary
    try:
        sess_sum = redis_upd.get("session_summary")
        if sess_sum and isinstance(sess_sum, dict):
            # Persist via store_short_term_context to ensure keys/expiry
            msg = sess_sum.get("value") or ""
            tasks.append(asyncio.create_task(store_short_term_context(session_id, msg)))
    except Exception:
        pass

    # Pinecone upsert
    try:
        pc_sum = pine_upd.get("session_summary")
        if pc_sum and isinstance(pc_sum, dict):
            tasks.append(asyncio.create_task(upsert_embedding(user_id, pc_sum.get("text") or "", {"kind": "session_summary"}, pc_sum.get("lifecycle_state") or "candidate")))
    except Exception:
        pass

    # Neo4j facts
    try:
        facts = neo4j_upd.get("facts") or {}
        for f in facts.get("facts", []):
            rel = (f or {}).get("relation") or "RELATED_TO"
            val = (f or {}).get("value") or ""
            if val:
                tasks.append(asyncio.create_task(merge_fact_relationship(user_id, "user", rel, str(val))))
    except Exception:
        pass

    # Profile DB set
    try:
        prof_set = profile_upd.get("set")
        if prof_set and isinstance(prof_set, dict):
            tasks.append(asyncio.create_task(update_user_profile(user_id, prof_set)))
    except Exception:
        pass

    # Run updates in parallel; errors are swallowed by helpers
    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    # Telemetry (best-effort)
    try:
        act_col = db_client.get_activity_logs_collection()
        if act_col:
            doc = {
                "type": "memory_updates",
                "user_id": str(user_id),
                "session_id": str(session_id),
                "sources": [k for k, v in (updates or {}).items() if v],
                "results": [False if isinstance(r, Exception) else bool(r) for r in results],
                "timestamp": datetime.utcnow(),
            }
            await run_in_threadpool(act_col.insert_one, doc)
    except Exception:
        pass

    return {"updated_sources": [k for k, v in (updates or {}).items() if v], "ok": all(False if isinstance(r, Exception) else bool(r) for r in results) if results else True}


async def recall_context(user_id: str, session_id: str, query_text: str) -> Dict[str, Any]:
    """Retrieve combined relevant context labeled by source with confidences.
    Runs queries in parallel and merges results.
    """
    async def _redis_part():
        try:
            data = await fetch_recent_context(session_id, last_n=10)
            return [{"source": "redis", "id": "recent", "snippet": "\n".join(data.get("messages") or []), "confidence": 0.65}]
        except Exception:
            return []

    async def _pinecone_part():
        try:
            rows = await query_user_memories(user_id, query_text or "", top_k=5)
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({
                    "source": "pinecone",
                    "id": str(r.get("memory_id") or ""),
                    "snippet": r.get("text") or "",
                    "confidence": float(r.get("similarity") or 0.0),
                })
            return out
        except Exception:
            return []

    async def _neo4j_part():
        try:
            facts = await get_user_facts(user_id)
            if facts:
                return [{"source": "neo4j", "id": "facts", "snippet": facts, "confidence": 0.7}]
            return []
        except Exception:
            return []

    parts = await asyncio.gather(_redis_part(), _pinecone_part(), _neo4j_part(), return_exceptions=True)
    merged: List[Dict[str, Any]] = []
    for p in parts:
        if isinstance(p, list):
            merged.extend(p)

    return {
        "user_id": str(user_id),
        "session_id": str(session_id),
        "query": query_text,
        "items": merged,
        "timestamp": datetime.utcnow().isoformat(),
    }


