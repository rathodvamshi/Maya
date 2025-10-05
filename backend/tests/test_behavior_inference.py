import types
import asyncio

from app.services import behavior_tracker

class FakeRedis:
    def __init__(self, data):
        # data: dict key -> dict of hash fields
        self.data = data
    async def hgetall(self, key):
        return self.data.get(key, {})

async def _run_case(fake_hash, expected_detail, expected_tone):
    # Patch redis_client
    behavior_tracker.redis_client = FakeRedis({"user:uid:behav": fake_hash})
    prefs = await behavior_tracker.get_inferred_preferences("uid")
    assert prefs["detail_level"] == expected_detail
    if expected_tone is None:
        assert prefs.get("tone_preference_inferred") is None
    else:
        assert prefs.get("tone_preference_inferred") == expected_tone


def test_inferred_preferences_mapping():
    # deep bias > 0.6
    deep_hash = {"depth_bias": "0.95", "tone_pref_counts.playful": "6", "tone_pref_counts.formal": "2"}
    # concise bias < -0.6
    concise_hash = {"depth_bias": "-1.2", "tone_pref_counts.supportive": "3", "tone_pref_counts.formal": "1"}
    # balanced bias mid + tone dominance threshold not met
    balanced_hash = {"depth_bias": "0.1", "tone_pref_counts.playful": "3", "tone_pref_counts.formal": "3"}

    asyncio.run(_run_case(deep_hash, "deep", "playful"))
    asyncio.run(_run_case(concise_hash, "concise", "supportive"))
    asyncio.run(_run_case(balanced_hash, "balanced", None))
