import pytest

from app.services.persona_response import generate_response


@pytest.mark.asyncio
async def test_low_confidence_forces_neutral():
    resp = await generate_response(
        "I guess that's fine",
        emotion="happy",
        confidence=0.10,  # below threshold -> neutral fallback
        base_ai_text="Great job!",
        user_id="u1",
    )
    # Heuristic: should not include strongly exuberant template markers if neutralized
    assert "happy" not in resp.lower()


@pytest.mark.asyncio
async def test_rotation_and_no_repeat():
    texts = []
    for _ in range(6):
        r = await generate_response(
            "I'm ok",
            emotion="neutral",
            confidence=0.9,
            base_ai_text="Alright",
            user_id="rot",
        )
        texts.append(r)
    assert len(set(texts)) > 1
