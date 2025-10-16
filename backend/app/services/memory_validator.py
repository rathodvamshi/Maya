# backend/app/services/memory_validator.py

from __future__ import annotations

from typing import Dict, Any
from datetime import datetime
import time
import logging

from fastapi.concurrency import run_in_threadpool

from app.services import redis_service
from app.services import pinecone_service
from app.services.neo4j_service import neo4j_service
from app.database import db_client

logger = logging.getLogger(__name__)


async def validate_memory_connections() -> Dict[str, Any]:
    """Validate Redis, Pinecone, Neo4j, and Profile DB connectivity + latency.
    Stores a summary row in activity_logs.
    """
    results: Dict[str, Any] = {"redis": {}, "pinecone": {}, "neo4j": {}, "profile_db": {}}

    # Redis
    try:
        start = time.perf_counter()
        ok = await redis_service.ping()
        results["redis"] = {"ok": bool(ok), "latency_ms": int((time.perf_counter() - start) * 1000)}
    except Exception as e:
        # retry once
        try:
            start = time.perf_counter()
            ok = await redis_service.ping()
            results["redis"] = {"ok": bool(ok), "latency_ms": int((time.perf_counter() - start) * 1000), "retry": True}
        except Exception as e2:
            results["redis"] = {"ok": False, "error": str(e2), "retry": True}

    # Pinecone (best-effort: query_relevant_summary for a trivial string)
    try:
        start = time.perf_counter()
        _ = await run_in_threadpool(pinecone_service.query_relevant_summary, "health-check", 1)
        results["pinecone"] = {"ok": True, "latency_ms": int((time.perf_counter() - start) * 1000)}
    except Exception as e:
        # retry once
        try:
            start = time.perf_counter()
            _ = await run_in_threadpool(pinecone_service.query_relevant_summary, "health-check", 1)
            results["pinecone"] = {"ok": True, "latency_ms": int((time.perf_counter() - start) * 1000), "retry": True}
        except Exception as e2:
            results["pinecone"] = {"ok": False, "error": str(e2), "retry": True}

    # Neo4j
    try:
        start = time.perf_counter()
        _ = await neo4j_service.get_user_facts("health-user")
        results["neo4j"] = {"ok": True, "latency_ms": int((time.perf_counter() - start) * 1000)}
    except Exception as e:
        # retry once
        try:
            start = time.perf_counter()
            _ = await neo4j_service.get_user_facts("health-user")
            results["neo4j"] = {"ok": True, "latency_ms": int((time.perf_counter() - start) * 1000), "retry": True}
        except Exception as e2:
            results["neo4j"] = {"ok": False, "error": str(e2), "retry": True}

    # Profile DB (Mongo): simple ping/find_one
    try:
        start = time.perf_counter()
        prof = db_client.get_user_profile_collection()
        if prof:
            await run_in_threadpool(prof.find_one, {"_id": "health-user"})
            results["profile_db"] = {"ok": True, "latency_ms": int((time.perf_counter() - start) * 1000)}
        else:
            results["profile_db"] = {"ok": False, "error": "No collection"}
    except Exception as e:
        # retry once
        try:
            start = time.perf_counter()
            prof = db_client.get_user_profile_collection()
            if prof:
                await run_in_threadpool(prof.find_one, {"_id": "health-user"})
                results["profile_db"] = {"ok": True, "latency_ms": int((time.perf_counter() - start) * 1000), "retry": True}
            else:
                results["profile_db"] = {"ok": False, "error": "No collection", "retry": True}
        except Exception as e2:
            results["profile_db"] = {"ok": False, "error": str(e2), "retry": True}

    # Activity logs
    try:
        act = db_client.get_activity_logs_collection()
        if act:
            await run_in_threadpool(act.insert_one, {
                "type": "memory_validation",
                "results": results,
                "timestamp": datetime.utcnow(),
            })
    except Exception:
        pass

    results["ok"] = all(v.get("ok") for v in results.values() if isinstance(v, dict) and "ok" in v)
    return results


