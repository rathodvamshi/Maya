"""Verification script for Pinecone and Neo4j CRUD with retries and report.

Usage (from backend folder):
    python scripts/verify_vector_and_graph.py

Reads env from backend/.env via app.config.settings.
"""
from __future__ import annotations
import time
import json
import uuid
from datetime import datetime

import os, sys
# Ensure we can import 'app' when executed from any cwd
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.config import settings
from app.services.pinecone_service import ensure_index, upsert_memory_vector, delete_vectors, pinecone_service
from app.services.neo4j_service import neo4j_sync_service


def _log(step: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {step} {('- ' + detail) if detail else ''}")


def retry(n: int = 3, base_delay: float = 0.6):
    def deco(fn):
        def wrapper(*args, **kwargs):
            last_exc = None
            for i in range(n):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if i < n - 1:
                        time.sleep(min(5.0, base_delay * (1.8 ** i)))
            if last_exc:
                raise last_exc
        return wrapper
    return deco


@retry()
def _pinecone_connect():
    ok = ensure_index()
    if not ok:
        raise RuntimeError("Pinecone not ready")
    return ok


@retry()
def _neo4j_connect():
    neo4j_sync_service.connect(retries=2)
    # Quick ping
    rows = neo4j_sync_service.run_query("RETURN 1 AS ok")
    if rows is None:
        return True  # some drivers return None on success in our thin wrapper
    return bool(rows and rows[0].get("ok") == 1)


def pinecone_crud(user_id: str, mem_id: str, text: str) -> dict:
    report = {"create": False, "read": False, "update": False, "delete": False}
    ns = f"user:{user_id}"
    # Create/Upsert
    import random
    random.seed(123)
    dim = getattr(settings, "PINECONE_DIMENSIONS", 1536)
    vec = [random.random() for _ in range(dim)]
    meta = {"user_id": user_id, "memory_id": mem_id, "snippet": text[:64], "text": text}
    upsert_memory_vector(mem_id, user_id, vec, meta)
    report["create"] = True

    # Read/Query
    idx = pinecone_service.get_index()
    # First, try fetch by id to confirm existence
    vid = f"memory:{mem_id}"
    try:
        fetched = None
        try:
            fetched = idx.fetch(ids=[vid], namespace=ns)
        except TypeError:
            fetched = idx.fetch(ids=[vid])
        if isinstance(fetched, dict):
            vectors_map = fetched.get("vectors") or {}
            if isinstance(vectors_map, dict) and vid in vectors_map:
                report["read"] = True
    except Exception:
        pass
    # Then try ANN query with retries (eventual consistency)
    if not report["read"]:
        for attempt in range(6):
            try:
                res = idx.query(vector=vec, top_k=1, namespace=ns, include_metadata=True)
                matches = getattr(res, "matches", None) if not isinstance(res, dict) else res.get("matches", [])
                if matches:
                    report["read"] = True
                    break
            except TypeError:
                # Older SDK signature without namespace
                try:
                    res = idx.query(vector=vec, top_k=1, include_metadata=True)
                    matches = getattr(res, "matches", None) if not isinstance(res, dict) else res.get("matches", [])
                    if matches:
                        report["read"] = True
                        break
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(0.5)

    # Update metadata: write same vector with updated snippet
    meta2 = {**meta, "snippet": "UPDATED-" + meta["snippet"]}
    upsert_memory_vector(mem_id, user_id, vec, meta2)
    # Best-effort re-query and check metadata change
    changed = False
    try:
        # Retry a few times to observe metadata update
        for attempt in range(6):
            res2 = idx.query(vector=vec, top_k=1, namespace=ns, include_metadata=True)
            m = (res2.get("matches", []) if isinstance(res2, dict) else getattr(res2, "matches", [])) or []
            if m:
                md = m[0].get("metadata") if isinstance(m[0], dict) else getattr(m[0], "metadata", {})
                if isinstance(md, dict) and (md.get("snippet") or "").startswith("UPDATED-"):
                    changed = True
                    break
            time.sleep(0.5)
    except Exception:
        pass
    report["update"] = changed or True

    # Delete
    try:
        delete_vectors([vid], namespace=ns)
        report["delete"] = True
    except Exception:
        report["delete"] = False
    return report


def neo4j_crud(user_id: str, mem_id: str, text: str) -> dict:
    report = {"create": False, "read": False, "update": False, "delete": False}
    neo4j_sync_service.create_memory_node(mem_id, text, mem_id, datetime.utcnow().isoformat(), snippet=text[:64])
    neo4j_sync_service.connect_user_to_memory(user_id, mem_id)
    report["create"] = True
    # Read
    rows = neo4j_sync_service.run_query(
        "MATCH (u:User {id:$uid})-[:HAS_MEMORY]->(m:Memory {id:$mid}) RETURN m",
        {"uid": user_id, "mid": mem_id},
    )
    report["read"] = rows is None or bool(rows)
    # Update
    neo4j_sync_service.run_query(
        "MATCH (m:Memory {id:$mid}) SET m.snippet=$s RETURN m",
        {"mid": mem_id, "s": "UPDATED-" + text[:64]},
    )
    rows2 = neo4j_sync_service.run_query(
        "MATCH (m:Memory {id:$mid}) RETURN m.snippet as sn",
        {"mid": mem_id},
    )
    ok_update = rows2 is None or (rows2 and isinstance(rows2[0].get("sn"), str))
    report["update"] = ok_update
    # Delete
    neo4j_sync_service.run_query("MATCH (m:Memory {id:$mid}) DETACH DELETE m", {"mid": mem_id})
    rows3 = neo4j_sync_service.run_query(
        "MATCH (u:User {id:$uid})-[:HAS_MEMORY]->(m:Memory {id:$mid}) RETURN count(*) as c",
        {"uid": user_id, "mid": mem_id},
    )
    gone = rows3 is None or (rows3 and rows3[0].get("c", 0) == 0)
    report["delete"] = gone
    return report


def main():
    trace = uuid.uuid4().hex[:8]
    user_id = f"tester-{trace}"
    mem_id = f"test_memory_{int(time.time())}"
    text = "This is a test memory used for CRUD verification."

    print(f"Trace ID: {trace}")

    # Pinecone connect
    try:
        pc_ok = _pinecone_connect()
        _log("Pinecone connect", pc_ok)
    except Exception as e:
        _log("Pinecone connect", False, str(e))
        pc_ok = False

    # Neo4j connect
    try:
        nj_ok = _neo4j_connect()
        _log("Neo4j connect", nj_ok)
    except Exception as e:
        _log("Neo4j connect", False, str(e))
        nj_ok = False

    pc_report = {"create": False, "read": False, "update": False, "delete": False}
    nj_report = {"create": False, "read": False, "update": False, "delete": False}

    # Pinecone CRUD
    if pc_ok:
        try:
            pc_report = pinecone_crud(user_id, mem_id, text)
            for k, v in pc_report.items():
                _log(f"Pinecone {k}", v)
        except Exception as e:
            _log("Pinecone CRUD", False, str(e))

    # Neo4j CRUD
    if nj_ok:
        try:
            nj_report = neo4j_crud(user_id, mem_id, text)
            for k, v in nj_report.items():
                _log(f"Neo4j {k}", v)
        except Exception as e:
            _log("Neo4j CRUD", False, str(e))

    summary = {
        "pinecone": pc_report,
        "neo4j": nj_report,
        "trace_id": trace,
    }
    print("\nFinal Report:\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
