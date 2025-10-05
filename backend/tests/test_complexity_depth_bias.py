import asyncio
from app.services import behavior_tracker


class FakePipeline:
    def __init__(self, store, key):
        self.store = store
        self.key = key
    def hincrby(self, key, field, amount):  # noqa: D401
        h = self.store.setdefault(key, {})
        h[field] = str(int(h.get(field, "0")) + int(amount))
        return self
    def hset(self, key, field, value):
        h = self.store.setdefault(key, {})
        h[field] = value
        return self
    def expire(self, key, ttl):
        # ignore ttl in test
        return self
    async def execute(self):
        return True


class FakeRedis:
    def __init__(self):
        self.store = {}
    def pipeline(self, transaction=False):  # noqa: D401
        return FakePipeline(self.store, None)
    async def hget(self, key, field):
        return self.store.get(key, {}).get(field)
    async def hgetall(self, key):
        return self.store.get(key, {})


def get_depth_bias(fake):
    data = fake.store.get("user:uid:behav", {})
    return float(data.get("depth_bias", "0") or 0)


def test_depth_bias_how_to_deep_positive():
    fake = FakeRedis()
    behavior_tracker.redis_client = fake
    asyncio.run(behavior_tracker.update_behavior_from_event(user_id="uid", complexity="how_to", answer_chars=620, tone_used=None))
    val = get_depth_bias(fake)
    # base 0.12 * 1.3 = 0.156 -> allow small rounding
    assert 0.15 <= val <= 0.16


def test_depth_bias_factual_long_reduced():
    fake = FakeRedis()
    behavior_tracker.redis_client = fake
    asyncio.run(behavior_tracker.update_behavior_from_event(user_id="uid", complexity="factual", answer_chars=620, tone_used=None))
    val = get_depth_bias(fake)
    # base 0.12 * 0.6 = 0.072
    assert 0.07 <= val <= 0.073


def test_depth_bias_factual_short_negative():
    fake = FakeRedis()
    behavior_tracker.redis_client = fake
    asyncio.run(behavior_tracker.update_behavior_from_event(user_id="uid", complexity="factual", answer_chars=70, tone_used=None))
    val = get_depth_bias(fake)
    # base -0.07 * 1.2 = -0.084
    assert -0.085 <= val <= -0.083


def test_depth_bias_concise_boundary():
    fake = FakeRedis()
    behavior_tracker.redis_client = fake
    asyncio.run(behavior_tracker.update_behavior_from_event(user_id="uid", complexity="general", answer_chars=90, tone_used=None))
    val = get_depth_bias(fake)
    # base -0.04 (general scale 1.0)
    assert -0.041 <= val <= -0.039