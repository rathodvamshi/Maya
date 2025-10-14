import asyncio
import pytest


@pytest.mark.anyio
async def test_memory_manager_crud(monkeypatch):
    # Lazy import to avoid import side effects
    from app.memory.manager import MemoryManager

    # ---------------- Fakes ----------------
    session_hist = {}
    session_state = {}
    pine_vectors = set()
    neo4j_edges = set()

    async def fake_append_session_messages(session_id, messages, max_items=50, ttl_seconds=86400):
        arr = session_hist.setdefault(session_id, [])
        for m in messages:
            arr.append({"role": m.get("role"), "content": m.get("content")})
        if len(arr) > max_items:
            del arr[:-max_items]

    async def fake_get_session_history(session_id, limit=50):
        return (session_hist.get(session_id, []) or [])[-limit:]

    async def fake_set_session_history(session_id, messages, ttl_seconds=86400):
        session_hist[session_id] = list(messages)

    async def fake_delete_session(session_id):
        session_hist.pop(session_id, None)

    async def fake_delete_session_state(session_id):
        session_state.pop(session_id, None)

    def fake_pine_query_user_memories(user_id, query_text, top_k=8):
        # Return deterministic match when query contains keyword
        out = []
        if "pizza" in (query_text or "").lower():
            out.append({"memory_id": "m1", "similarity": 0.91, "text": "user likes pizza", "lifecycle_state": "active"})
        return out

    def fake_pine_delete_user_memory_vectors(user_id, memory_id):
        pine_vectors.discard(f"memory:{memory_id}")

    async def fake_neo_get_user_facts(user_id):
        return "; ".join(sorted(e for e in neo4j_edges if e.startswith(f"{user_id}:"))).replace(f"{user_id}:", "")

    async def fake_neo_create_relation(user_id, rel, concept):
        neo4j_edges.add(f"{user_id}:{rel}->{concept}")

    async def fake_neo_delete_relation(user_id, rel, concept):
        neo4j_edges.discard(f"{user_id}:{rel}->{concept}")

    async def fake_neo_delete_concept(concept):
        to_del = [e for e in list(neo4j_edges) if e.endswith(f"->{concept}")]
        for e in to_del:
            neo4j_edges.discard(e)

    async def fake_create_memory(data):
        # Simulate Mongo insert + Pinecone upsert side-effect by tracking vector id
        pine_vectors.add("memory:m1")
        return {"_id": "m1", "title": data.get("title"), "value": data.get("value")}

    async def fake_update_memory(user_id, memory_id, patch, reason="update"):
        # Accept updates and keep vector present
        return {"_id": memory_id, **patch}

    # ---------------- Monkeypatch wiring ----------------
    import app.services.memory_store as ms
    import app.services.pinecone_service as pcs
    import app.services.neo4j_service as n4j
    import app.services.memory_service as mems

    monkeypatch.setattr(ms, "append_session_messages", fake_append_session_messages)
    monkeypatch.setattr(ms, "get_session_history", fake_get_session_history)
    monkeypatch.setattr(ms, "set_session_history", fake_set_session_history)
    monkeypatch.setattr(ms, "delete_session", fake_delete_session)
    monkeypatch.setattr(ms, "delete_session_state", fake_delete_session_state)

    monkeypatch.setattr(pcs, "query_user_memories", fake_pine_query_user_memories)
    monkeypatch.setattr(pcs, "delete_user_memory_vectors", fake_pine_delete_user_memory_vectors)

    monkeypatch.setattr(n4j.neo4j_service, "get_user_facts", fake_neo_get_user_facts)
    monkeypatch.setattr(n4j.neo4j_service, "create_relation", fake_neo_create_relation)
    monkeypatch.setattr(n4j.neo4j_service, "delete_relation", fake_neo_delete_relation)
    monkeypatch.setattr(n4j.neo4j_service, "delete_concept", fake_neo_delete_concept)

    monkeypatch.setattr(mems, "create_memory", fake_create_memory)
    monkeypatch.setattr(mems, "update_memory", fake_update_memory)

    mm = MemoryManager()

    user_id = "u1"
    session_id = "s1"

    # --- Short-term: add + get + update + delete ---
    r = await mm.add_memory(user_id, {"role": "user", "content": "Hello"}, memory_type="short-term", session_id=session_id)
    assert r.get("ok") is True
    got = await mm.get_memory(user_id, memory_type="short-term", session_id=session_id)
    assert got["history"][0]["content"] == "Hello"

    # Update history
    r = await mm.update_memory(user_id, {"messages": [{"role": "assistant", "content": "Hi"}]}, "short-term", session_id=session_id)
    assert r["ok"] is True
    got = await mm.get_memory(user_id, memory_type="short-term", session_id=session_id)
    assert got["history"][0]["content"] == "Hi"

    # --- Long-term: create + query + delete ---
    r = await mm.add_memory(user_id, {"title": "favorite_food", "value": "loves pizza"}, memory_type="long-term")
    assert r.get("ok") is True and r.get("id") == "m1"
    q = await mm.get_memory(user_id, query="what food", memory_type="long-term")
    assert q["pinecone"] and q["pinecone"][0]["memory_id"] == "m1"
    # Delete
    r = await mm.delete_memory(user_id, "long-term", identifier="m1")
    assert r["ok"] is True

    # --- Semantic: create relation + read + update + delete ---
    r = await mm.add_memory(user_id, {"relation": "LIKES", "concept": "pizza"}, memory_type="semantic")
    assert r["ok"] is True
    g = await mm.get_memory(user_id, memory_type="semantic")
    assert "LIKES -> pizza" in g["neo4j"]
    # Update relation target
    r = await mm.update_memory(user_id, {"relation": "LIKES", "old_concept": "pizza", "concept": "pasta"}, "semantic")
    assert r["ok"] is True
    g = await mm.get_memory(user_id, memory_type="semantic")
    assert "LIKES -> pasta" in g["neo4j"] and "LIKES -> pizza" not in g["neo4j"]
    # Delete relation
    r = await mm.delete_memory(user_id, "semantic", identifier="LIKES:pasta")
    assert r["ok"] is True
    g = await mm.get_memory(user_id, memory_type="semantic")
    assert "LIKES -> pasta" not in g["neo4j"]


