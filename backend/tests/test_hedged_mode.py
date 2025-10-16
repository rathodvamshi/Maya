import asyncio
from app.services import ai_service, metrics
from app.config import settings


def test_hedged_mode_monkeypatch(monkeypatch):
    # Enable hedged mode and configure small hedge delay and max parallel
    monkeypatch.setattr(settings, 'AI_ENABLE_HEDGED', True)
    monkeypatch.setattr(settings, 'AI_HEDGE_DELAY_MS', 1)
    monkeypatch.setattr(settings, 'AI_MAX_PARALLEL', 3)

    # With Gemini-only stack, hedging should not crash; ensure single provider path works
    monkeypatch.setattr(ai_service, 'AI_PROVIDERS', ['gemini'])

    def _fast_gemini(prompt: str) -> str:
        return 'gemini-reply'
    monkeypatch.setattr(ai_service, '_try_gemini', _fast_gemini)

    # Reset metrics counters used
    metrics._COUNTERS.pop('chat.hedge.enabled', None)
    metrics._COUNTERS = {k: v for k, v in metrics._COUNTERS.items() if not k.startswith('chat.hedge.win.provider.')}

    out = asyncio.run(ai_service.get_response(prompt='Hello hedged test', history=[]))
    assert 'gemini' in out or 'reply' in out
    # Hedge may still be marked enabled by config; ensure no winner metric for secondary provider
    _ = metrics._COUNTERS.get('chat.hedge.enabled', 0)
    assert not any(k.startswith('chat.hedge.win.provider.') for k in metrics._COUNTERS)
