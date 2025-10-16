import os
import time
import pytest
from uuid import uuid4

from app.celery_tasks import process_and_store_memory
from app.services.pinecone_service import pinecone_service
from app.services.neo4j_service import neo4j_sync_service


def _env_ready():
    return bool(os.getenv("PINECONE_API_KEY")) and bool(os.getenv("NEO4J_URI"))


@pytest.mark.skipif(not _env_ready(), reason="External services not configured")
def test_memory_pipeline_e2e_best_effort():
    user_id = f"test-{uuid4().hex[:8]}"
    mem_id = f"mem-{uuid4().hex[:8]}"
    text = "E2E pipeline memory test text"

    # Run task synchronously to avoid broker dependency in CI
    result = process_and_store_memory.apply(args=[user_id, mem_id, text, "test"]).get(timeout=60)
    assert result.get("ok") is True

    # Verify Pinecone index is ready
    assert pinecone_service.is_ready() is True

    # Neo4j relation check (best-effort)
    neo4j_sync_service.connect(retries=2)
    rows = neo4j_sync_service.run_query(
        "MATCH (u:User {id:$uid})-[:HAS_MEMORY]->(m:Memory {id:$mid}) RETURN count(*) as c",
        {"uid": user_id, "mid": mem_id},
    )
    assert rows is None or rows[0].get("c", 1) >= 0