from app.services import ai_service


class DummyBehavior:
    def __init__(self):
        self.calls = 0
    async def get(self, uid):  # not used
        return {}

dummy_calls = {"n": 0}

async def _fake_inferred(uid: str):
    dummy_calls["n"] += 1
    return {"detail_level": "deep", "tone_preference_inferred": "playful", "depth_bias": 0.9}


def test_inferred_prefs_lru_cache(monkeypatch):
    # Clear cache
    if hasattr(ai_service, "_INFER_PREFS_CACHE"):
        ai_service._INFER_PREFS_CACHE.clear()
    # Patch behavior_tracker.get_inferred_preferences used internally via imported symbol
    from app.services import behavior_tracker
    monkeypatch.setattr(behavior_tracker, "get_inferred_preferences", _fake_inferred)

    # Build minimal profile containing user_id
    profile = {"user_id": "user123"}
    # First call should populate cache
    import asyncio
    asyncio.run(ai_service.get_response(prompt="Hello", history=[], profile=profile))
    first_calls = dummy_calls["n"]
    # Second call should use cache (no increment)
    asyncio.run(ai_service.get_response(prompt="Hello again", history=[], profile=profile))
    second_calls = dummy_calls["n"]
    assert first_calls == second_calls, "Expected cached inferred prefs to prevent extra call"