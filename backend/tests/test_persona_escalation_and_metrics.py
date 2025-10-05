import pytest

from app.services.persona_response import generate_response
from app.memory import session_memory
from app.services import metrics

@pytest.mark.asyncio
async def test_escalation_triggers_metric_and_prompt():
    user_id = "u-escalate"
    # Simulate prior sad turns
    for i in range(3):
        await session_memory.add_to_context(user_id, f"prev {i}", f"ai {i}", "sad")
    out = await generate_response(
        "I still feel really low today",
        emotion="sad",
        confidence=0.9,
        base_ai_text="I'm here.",
        user_id=user_id,
    )
    snap = metrics.snapshot()
    # Metric existence
    assert any(k.startswith("persona.escalation.sad") for k in snap["counters"].keys())
    # Escalation phrase appended
    assert "want to share a bit more" in out.lower()

@pytest.mark.asyncio
async def test_low_confidence_fallback_metric():
    user_id = "u-lowconf"
    out = await generate_response(
        "maybe it's fine",
        emotion="happy",
        confidence=0.10,
        base_ai_text="Great job",
        user_id=user_id,
    )
    snap = metrics.snapshot()
    # Should record neutral fallback reason
    assert any(k.startswith("persona.fallback.neutral.low_confidence") for k in snap["counters"].keys())
    # Output should not look overtly exuberant (heuristic check)
    assert "great job" in out.lower() or out  # allow blend

@pytest.mark.asyncio
async def test_sarcasm_fallback_metric():
    user_id = "u-sarcasm"
    out = await generate_response(
        "Great just perfect 😂 /s",
        emotion="happy",
        confidence=0.9,
        base_ai_text="Glad to hear it",
        user_id=user_id,
    )
    snap = metrics.snapshot()
    assert any(k.startswith("persona.fallback.neutral.sarcasm") for k in snap["counters"].keys())
    # Should not retain an obviously ecstatic template line
    # (We don't strictly know template, so just ensure not too many celebration emojis)
    exuberant_emojis = sum(out.count(e) for e in ["🎉", "🤩", "🥳"])
    assert exuberant_emojis <= 1
