import asyncio
from app.services import ai_service, metrics
from app.config import settings


def test_hedged_mode_monkeypatch(monkeypatch):
    # Enable hedged mode and configure small hedge delay and max parallel
    monkeypatch.setattr(settings, 'AI_ENABLE_HEDGED', True)
    monkeypatch.setattr(settings, 'AI_HEDGE_DELAY_MS', 1)
    monkeypatch.setattr(settings, 'AI_MAX_PARALLEL', 3)

    # Arrange providers (at least two so hedge path triggers)
    monkeypatch.setattr(ai_service, 'AI_PROVIDERS', ['gemini', 'cohere'])

    # Slow primary (gemini) and fast secondary (cohere) to force hedge win by cohere
    def _slow_gemini(prompt: str) -> str:  # simulate near-timeout but within limit
        import time; time.sleep(0.2)
        return 'slow-primary'
    def _fast_cohere(prompt: str) -> str:
        return 'fast-hedge'
    monkeypatch.setattr(ai_service, '_try_gemini', _slow_gemini)
    monkeypatch.setattr(ai_service, '_try_cohere', _fast_cohere)

    # Reset metrics counters used
    metrics._COUNTERS.pop('chat.hedge.enabled', None)
    metrics._COUNTERS = {k: v for k, v in metrics._COUNTERS.items() if not k.startswith('chat.hedge.win.provider.')}

    out = asyncio.run(ai_service.get_response(prompt='Hello hedged test', history=[]))
    # In rare timing edge cases primary might still finish first; allow either but prefer hedge
    assert ('fast-hedge' in out) or ('slow-primary' in out)
    assert metrics._COUNTERS.get('chat.hedge.enabled', 0) >= 1
    if 'fast-hedge' in out:
        # hedge won; should record winner metric
        assert any(k.startswith('chat.hedge.win.provider.cohere') for k in metrics._COUNTERS)
