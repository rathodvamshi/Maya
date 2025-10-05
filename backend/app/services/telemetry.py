"""Telemetry Event Logging Service (Phase 1)

Lightweight, fire-and-forget logging of interaction events. Events are inserted
directly into Mongo synchronously for now (low volume assumption) with a future
path to batching / queueing.

Schema (interaction_events collection):
{
  user_id: str,
  session_id: str | None,
  ts: datetime,
  user_message: str,
  assistant_answer: str,
  emotion: {label, confidence} | None,
  tone: str | None,
  suggestions: [str],
  provider: str | None,
  answer_chars: int,
  answer_tokens_est: int,
  complexity: str | None
}

Complexity classification kept trivial (heuristic) in Phase 1.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from pymongo.collection import Collection
from app.database import db_client

logger = logging.getLogger(__name__)

INTERACTION_COLLECTION = "interaction_events"

def _get_collection() -> Collection | None:
    """Return the Mongo collection if DB is healthy; otherwise None.

    Avoids import-time failures when Mongo isn't available at startup.
    """
    try:
        if getattr(db_client, "healthy", lambda: False)():
            # Lazily access underlying db only when healthy
            return db_client.db[INTERACTION_COLLECTION]  # type: ignore[index]
    except Exception:
        pass
    return None


def classify_complexity(user_message: str, answer: str) -> str:
    """Heuristic complexity classifier (Phase 1.5 refined).

    Order matters (first match wins for some categories):
      - how_to: presence of instructional markers ("how do i", "how to", multiple step indicators like '1.' '2.')
      - recommendation: verbs suggesting choice / selection (recommend, suggest, best, which should I)
      - explanatory: contains explain/why/meaning/difference between
      - factual: short direct "what is X" / "who is" / "capital of" queries (< 60 chars)
      - chitchat: greeting / pleasantry patterns and short length
      - general fallback
    Additionally, answer length can upgrade factual -> explanatory if answer is long (>350 chars) and contains section markers.
    """
    q = user_message.strip().lower()
    if not q:
        return "general"
    step_markers = sum(1 for tok in ["1.", "2.", "3.", "1)", "2)", "step 1", "step 2"] if tok in q)
    if any(p in q for p in ["how do i", "how to ", "how can i"]) or ("install" in q and "how" in q) or step_markers >= 2:
        return "how_to"
    if any(p in q for p in ["recommend", "suggest", "which should", "best "]):
        return "recommendation"
    if any(p in q for p in ["explain", "why ", "meaning", "difference between", "how does"]):
        return "explanatory"
    if len(q) < 60 and (q.startswith("what is") or q.startswith("who is") or "capital of" in q or q.startswith("when is")):
        label = "factual"
        # Potential upgrade after seeing answer
        upgrade = False
        if len(answer) > 300 and answer.count("\n") >= 2 and any(x in answer.lower() for x in ["first", "second", "in summary", "overall"]):
            upgrade = True
        return "explanatory" if upgrade else label
    if len(q) < 40 and any(p == q or q.startswith(p) for p in ["hi", "hello", "hey", "thanks", "thank you", "good morning", "good evening", "good night"]):
        return "chitchat"
    # Upgrade rule: long structured answer suggests explanatory depth
    if len(answer) > 350 and answer.count("\n") >= 2 and any(x in answer.lower() for x in ["in summary", "overall", "first", "second"]):
        return "explanatory"
    return "general"


def log_interaction_event(
    *,
    user_id: Optional[str],
    session_id: Optional[str],
    user_message: str,
    assistant_answer: str,
    emotion: Optional[Dict[str, Any]] = None,
    tone: Optional[str] = None,
    suggestions: Optional[List[str]] = None,
    provider: Optional[str] = None,
) -> None:
    try:
        doc = {
            "user_id": user_id,
            "session_id": session_id,
            "ts": datetime.utcnow(),
            "user_message": user_message[:4000],
            "assistant_answer": assistant_answer[:8000],
            "emotion": emotion,
            "tone": tone,
            "suggestions": suggestions or [],
            "provider": provider,
            "answer_chars": len(assistant_answer),
            "answer_tokens_est": max(1, len(assistant_answer.split())),
        }
        doc["complexity"] = classify_complexity(user_message, assistant_answer)
        col = _get_collection()
        if col is not None:
            col.insert_one(doc)
        else:
            # Silent no-op when DB isn't available to avoid breaking request flow
            logger.debug("Telemetry skipped: Mongo not available")
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log interaction event", exc_info=True)


__all__ = ["log_interaction_event", "classify_complexity"]
