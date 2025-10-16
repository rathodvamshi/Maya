import os
import pytest
from app.config import settings
from app.services.pinecone_service import initialize_pinecone, pinecone_service, ensure_index
from app.services.pinecone_service import upsert_memory_vector, delete_vectors


def _has_pinecone():
    return bool(os.getenv("PINECONE_API_KEY"))


@pytest.mark.skipif(not _has_pinecone(), reason="Pinecone not configured")
def test_ensure_index_and_upsert_delete():
    assert ensure_index() is True
    idx = pinecone_service.get_index()
    assert idx is not None

    # Upsert a deterministic small vector of correct length
    import random
    random.seed(42)
    dim = getattr(settings, "PINECONE_DIMENSIONS", 1536)
    vec = [random.random() for _ in range(dim)]
    user_id = "test-user"
    mem_id = "mem-unit-1"
    upsert_memory_vector(mem_id, user_id, vec, {"text": "hello world"})
    # Query similarity
    idx = pinecone_service.get_index()
    try:
        res = idx.query(vector=vec, top_k=1, namespace=f"user:{user_id}", include_metadata=True)
        matches = getattr(res, "matches", None) if not isinstance(res, dict) else res.get("matches", [])
        assert matches is not None
    except TypeError:
        pass

    # Delete
    delete_vectors([f"memory:{mem_id}"], namespace=f"user:{user_id}")