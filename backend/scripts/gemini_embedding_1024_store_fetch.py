"""Gemini 1024-d embedding -> Pinecone store/fetch verification.

Usage (from backend/ root or repo root):
  python backend/scripts/gemini_embedding_1024_store_fetch.py

Relies on backend/.env via app.config.settings for configuration.
"""
from __future__ import annotations

import os
import sys
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.config import settings
from app.services import gemini_service
from app.services.pinecone_service import ensure_index, pinecone_service, upsert_memory_vector, delete_vectors


def main() -> int:
    required = getattr(settings, "PINECONE_DIMENSIONS", 1024)

    if not ((settings.GEMINI_API_KEYS and settings.GEMINI_API_KEYS.strip()) or (settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())):
        print("[SKIP] GEMINI_API_KEY(S) not configured in backend/.env")
        return 0
    if not settings.PINECONE_API_KEY:
        print("[SKIP] PINECONE_API_KEY not configured in backend/.env")
        return 0

    print(f"Target dimension: {required}")
    ok_pc = ensure_index()
    print(f"Pinecone ready: {ok_pc}")
    if not ok_pc:
        return 2

    text = f"Gemini 1024-d store/fetch {uuid.uuid4().hex}"
    try:
        emb = gemini_service.create_embedding(text, retries=3)
    except Exception as e:
        print(f"[FAIL] Gemini embedding error: {e}")
        return 2

    if not emb or len(emb) != required:
        print(f"[FAIL] Dimension mismatch. Expected {required}, got {len(emb) if emb else 'None'}")
        return 2

    user_id = "script-gemini-" + uuid.uuid4().hex[:8]
    mem_id = "mem-" + uuid.uuid4().hex[:8]
    ns = f"user:{user_id}"
    vid = f"memory:{mem_id}"
    metadata = {"user_id": user_id, "memory_id": mem_id, "text": text, "kind": "memory"}

    upsert_memory_vector(mem_id, user_id, emb, metadata)

    idx = pinecone_service.get_index()
    found = False

    # Try fetch by ID first (with namespace) then fall back to ANN query
    for _ in range(10):
        try:
            try:
                f = idx.fetch(ids=[vid], namespace=ns)
            except TypeError:
                f = idx.fetch(ids=[vid])
            if isinstance(f, dict):
                vectors_map = f.get("vectors") or {}
                if isinstance(vectors_map, dict) and vid in vectors_map:
                    found = True
                    break
        except Exception:
            pass
        time.sleep(0.5)

    if not found:
        for _ in range(10):
            try:
                try:
                    res = idx.query(vector=emb, top_k=1, namespace=ns, include_metadata=True)
                except TypeError:
                    res = idx.query(vector=emb, top_k=1, include_metadata=True)
                matches = (res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", [])) or []
                if matches:
                    found = True
                    break
            except Exception:
                pass
            time.sleep(0.5)

    try:
        delete_vectors([vid], namespace=ns)
    except Exception:
        pass

    if found:
        print("[PASS] Gemini 1024-d embedding stored and fetched from Pinecone.")
        return 0
    else:
        print("[FAIL] Vector not observable in Pinecone fetch/query.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
