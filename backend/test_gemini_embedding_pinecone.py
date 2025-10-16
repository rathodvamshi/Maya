import os
import time
import uuid
import pytest

from app.config import settings
from app.services import gemini_service
from app.services.pinecone_service import ensure_index, pinecone_service, upsert_memory_vector, delete_vectors


def _has_gemini_keys() -> bool:
    return bool((settings.GEMINI_API_KEYS and settings.GEMINI_API_KEYS.strip()) or (settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip()))


pytestmark = [
    pytest.mark.skipif(not _has_gemini_keys(), reason="GEMINI_API_KEY(S) not configured"),
    pytest.mark.skipif(not settings.PINECONE_API_KEY, reason="PINECONE_API_KEY not configured"),
]


def test_gemini_embedding_1024_pinecone_store_fetch():
    required = getattr(settings, "PINECONE_DIMENSIONS", 1024)
    # Ensure Pinecone index is ready and matches required dimension
    assert ensure_index(), "Pinecone index not ready"

    # Create a 1024-d embedding using Gemini service
    text = f"Gemini embedding 1024-d smoke test {uuid.uuid4().hex}"
    emb = gemini_service.create_embedding(text, retries=2)
    assert isinstance(emb, list) and len(emb) == required, f"Expected {required}, got {len(emb) if emb else 'None'}"

    # Upsert into Pinecone under a user namespace
    user_id = "pytest-gemini-" + uuid.uuid4().hex[:8]
    mem_id = "mem-" + uuid.uuid4().hex[:8]
    ns = f"user:{user_id}"
    vid = f"memory:{mem_id}"
    metadata = {"user_id": user_id, "memory_id": mem_id, "text": text, "kind": "memory"}

    upsert_memory_vector(mem_id, user_id, emb, metadata)

    # Fetch and query with small retries to account for eventual consistency
    idx = pinecone_service.get_index()
    found = False
    for _ in range(8):
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
        # Try ANN query as alternative proof of presence
        for _ in range(8):
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
    finally:
        pass

    assert found, "Vector not found in Pinecone via fetch/query"
