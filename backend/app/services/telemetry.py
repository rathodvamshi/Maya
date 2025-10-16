# backend/app/services/telemetry.py

from __future__ import annotations

from typing import Dict, Any, Optional, List
from datetime import datetime
import time
import logging

from fastapi.concurrency import run_in_threadpool

from app.database import db_client

logger = logging.getLogger(__name__)


class Stopwatch:
    def __init__(self):
        self._start = time.perf_counter()
    def ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)


async def log_pipeline_summary(user_id: str, session_id: str, summary: Dict[str, Any]) -> None:
    """Write a single summary row for observability dashboards (best-effort)."""
    try:
        act = db_client.get_activity_logs_collection()
        if act:
            payload = {
                "type": "pipeline_summary",
                "user_id": str(user_id),
                "session_id": str(session_id),
                "summary": summary,
                "timestamp": datetime.utcnow(),
            }
            await run_in_threadpool(act.insert_one, payload)
    except Exception:
        try:
            logger.debug("log_pipeline_summary failed", exc_info=True)
        except Exception:
            pass


async def log_provider_usage(provider: Optional[str], stage: str, duration_ms: int, ok: bool) -> None:
    try:
        act = db_client.get_activity_logs_collection()
        if act:
            await run_in_threadpool(act.insert_one, {
                "type": "provider_usage",
                "provider": provider,
                "stage": stage,
                "duration_ms": int(duration_ms),
                "ok": bool(ok),
                "timestamp": datetime.utcnow(),
            })
    except Exception:
        pass


# -----------------------------
# Pipeline metrics + aggregations
# -----------------------------
async def log_pipeline_metrics(
    *,
    pipeline_span: str,
    user_id: str,
    session_id: str,
    timings: Dict[str, Any],
    success_rate: float,
    failures: Optional[List[str]] = None,
) -> None:
    """Log a structured pipeline metrics document into activity_logs.

    Document schema matches requested format.
    """
    try:
        act = db_client.get_activity_logs_collection()
        if not act:
            return
        doc = {
            "type": "pipeline_metrics",
            "pipeline_span": pipeline_span,
            "user_id": str(user_id),
            "session_id": str(session_id),
            "timings": {k: int(v) for k, v in (timings or {}).items()},
            "success_rate": float(success_rate),
            "failures": list(failures or []),
            "timestamp": datetime.utcnow(),
        }
        await run_in_threadpool(act.insert_one, doc)
    except Exception:
        try:
            logger.debug("log_pipeline_metrics failed", exc_info=True)
        except Exception:
            pass


async def aggregate_average_latency(last_n: int = 50) -> Dict[str, float]:
    """Compute average per-stage latency over the last N pipeline metrics docs."""
    out: Dict[str, float] = {}
    try:
        col = db_client.get_activity_logs_collection()
        if not col:
            return out
        cur = col.find({"type": "pipeline_metrics"}).sort("timestamp", -1).limit(int(last_n))
        docs = await run_in_threadpool(lambda: list(cur))
        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for d in docs:
            for k, v in (d.get("timings") or {}).items():
                try:
                    sums[k] = sums.get(k, 0.0) + float(v)
                    counts[k] = counts.get(k, 0) + 1
                except Exception:
                    continue
        for k in sums:
            out[k] = round(sums[k] / max(1, counts.get(k, 1)), 2)
    except Exception:
        pass
    return out


async def aggregate_provider_success(last_n: int = 100) -> Dict[str, Any]:
    """Compute provider success rate from provider_usage docs over last N entries."""
    result: Dict[str, Any] = {"success_rate": {}, "counts": {}}
    try:
        col = db_client.get_activity_logs_collection()
        if not col:
            return result
        cur = col.find({"type": "provider_usage"}).sort("timestamp", -1).limit(int(last_n))
        docs = await run_in_threadpool(lambda: list(cur))
        ok_counts: Dict[str, int] = {}
        total_counts: Dict[str, int] = {}
        for d in docs:
            prov = (d.get("provider") or "unknown").lower()
            total_counts[prov] = total_counts.get(prov, 0) + 1
            if d.get("ok"):
                ok_counts[prov] = ok_counts.get(prov, 0) + 1
        for p, tot in total_counts.items():
            result["counts"][p] = tot
            result["success_rate"][p] = round((ok_counts.get(p, 0) / tot) if tot else 0.0, 3)
    except Exception:
        pass
    return result


async def log_provider_usage_summary() -> None:
    """Emit a summary snapshot to activity_logs for ops dashboards."""
    try:
        from app.services.redis_service import fetch_adaptive_stats
        stats = await fetch_adaptive_stats()
    except Exception:
        stats = {}
    try:
        col = db_client.get_activity_logs_collection()
        if not col:
            return
        await run_in_threadpool(col.insert_one, {
            "type": "provider_usage_summary",
            "snapshot": stats,
            "timestamp": datetime.utcnow(),
        })
    except Exception:
        pass


# -----------------------------
# Optional OpenTelemetry integration (disabled by default)
# -----------------------------
_OTEL_ENABLED = False
try:
    import os as _os
    _OTEL_ENABLED = (_os.getenv("TELEMETRY_OTEL_ENABLE", "false").lower() == "true")
    if _OTEL_ENABLED:
        # Optional import; if not installed, we keep disabled
        from opentelemetry import trace as _otel_trace  # type: ignore
        _otel_tracer = _otel_trace.get_tracer(__name__)
    else:
        _otel_tracer = None
except Exception:
    _OTEL_ENABLED = False
    _otel_tracer = None


def start_span(name: str):  # pragma: no cover simple wrapper
    if _OTEL_ENABLED and _otel_tracer is not None:
        try:
            return _otel_tracer.start_as_current_span(name)
        except Exception:
            return _nullctx()
    return _nullctx()


class _nullctx:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False

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
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from pymongo.collection import Collection
from app.database import db_client

logger = logging.getLogger(__name__)

INTERACTION_COLLECTION = "interaction_events"

def _get_collection() -> Collection | None:
    """Return the Mongo collection, using in-memory fallback when DB isn't ready.

    db_client.db property returns a real DB when connected or an in-memory stub
    otherwise. This lets logging proceed in tests/degraded mode.
    """
    try:
        db = getattr(db_client, "db", None)
        if db is None:
            return None
        return db[INTERACTION_COLLECTION]  # type: ignore[index]
    except Exception:
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
