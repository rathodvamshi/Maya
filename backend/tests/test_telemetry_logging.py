import uuid
from app.services.telemetry import log_interaction_event, INTERACTION_COLLECTION
from app.database import db_client


def test_log_interaction_inserts_document():
    user_id = f"testuser-{uuid.uuid4()}"
    message = "What is the capital of France?"
    answer = "Paris is the capital of France. ➝ Want a brief history?"
    # Ensure clean slate (best-effort)
    col = db_client.db[INTERACTION_COLLECTION]
    # Insert
    log_interaction_event(
        user_id=user_id,
        session_id=None,
        user_message=message,
        assistant_answer=answer,
        emotion={"label": "neutral", "confidence": 0.15},
        tone="neutral",
        suggestions=["➝ Want a brief history?"],
        provider="mock-provider",
    )
    doc = col.find_one({"user_id": user_id, "user_message": message})
    assert doc is not None, "Telemetry document not found in collection"
    assert doc.get("assistant_answer", "").startswith("Paris"), "Answer not stored correctly"
    assert doc.get("suggestions") == ["➝ Want a brief history?"], "Suggestions not stored"
    assert doc.get("answer_chars") == len(answer)
    assert doc.get("complexity") in {"factual", "explanatory", "general"}
