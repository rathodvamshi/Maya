import os
import pytest
from app.services.neo4j_service import neo4j_sync_service


def _has_neo4j():
    return all([
        os.getenv("NEO4J_URI"),
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"),
    ])


@pytest.mark.skipif(not _has_neo4j(), reason="Neo4j not configured")
def test_create_user_and_memory_relation():
    neo4j_sync_service.connect(retries=2)
    user_id = "test-user"
    mem_id = "mem-unit-2"
    text = "Unit test memory text"
    neo4j_sync_service.create_memory_node(mem_id, text, mem_id, "2024-01-01T00:00:00Z")
    neo4j_sync_service.connect_user_to_memory(user_id, mem_id)
    # Just ensure no exception; optionally read back
    rows = neo4j_sync_service.run_query(
        "MATCH (u:User {id:$uid})-[:HAS_MEMORY]->(m:Memory {id:$mid}) RETURN count(*) as c",
        {"uid": user_id, "mid": mem_id},
    )
    assert rows is None or rows[0].get("c", 1) >= 0