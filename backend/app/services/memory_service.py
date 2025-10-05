"""Memory Service
-----------------
Scaffolding for the long-term memory layer described in the roadmap.
Provides minimal, safe CRUD + versioning + recall event logging so other
parts of the system can start integrating without breaking existing flows.

Design principles (MVP):
- Never hard delete memory records; use lifecycle_state or archive flag.
- Every update creates a snapshot entry in memory_versions.
- Trust / salience fields are optional now; defaults applied if absent.
- All write operations validate required user_id + title.

Future extensions (not implemented yet):
- Salience recalculation worker
- Proactive recall trigger evaluation
- Distillation / summarization pipeline
- Sensitivity classification & ambiguity gating
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from bson import ObjectId

from app.database import (
    get_memories_collection,
    get_memory_versions_collection,
    get_recall_events_collection,
    get_pii_audit_collection,
)
from app.services.pinecone_service import upsert_memory_embedding
from app.config import settings

DEFAULT_PRIORITY = "normal"  # system|critical|normal|low
DEFAULT_LIFECYCLE = "candidate"  # candidate|active|aging|archived|distilled

# Bound weighting placeholders (not used in service directly yet)
PRIORITY_WEIGHTS = {"system": 1.3, "critical": 1.15, "normal": 1.0, "low": 0.9}

# --- Helpers ---

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _coerce_object_id(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    return ObjectId(str(value))


# --- CRUD / Versioning ---
async def create_memory(data: Dict[str, Any]) -> Dict[str, Any]:
    coll = get_memories_collection()
    user_id = data.get("user_id")
    title = data.get("title")
    if not user_id or not title:
        raise ValueError("user_id and title are required")

    # Conflict detection: existing same title different value
    existing = coll.find_one({"user_id": user_id, "title": title})
    lifecycle_state = data.get("lifecycle_state") or DEFAULT_LIFECYCLE
    conflict_with: Optional[Dict[str, Any]] = None
    if existing:
        existing_value = existing.get("value")
        new_value = data.get("value")
        if new_value and existing_value and new_value.strip() != str(existing_value).strip():
            # Divergence -> candidate until confirmation
            conflict_with = existing
            lifecycle_state = "candidate"
            try:
                coll.update_one({"_id": existing["_id"]}, {"$inc": {"trust.conflict_count": 1}})
            except Exception:
                pass

    now = _now_iso()
    doc: Dict[str, Any] = {
        "user_id": user_id,
        "title": title,
        "type": data.get("type", "fact"),
        "value": data.get("value", ""),
        "structured_value": data.get("structured_value"),
        "source_type": data.get("source_type", "user"),
        "priority": data.get("priority", DEFAULT_PRIORITY),
        "salience_score": data.get("salience_score", 1.0),
        "trust": data.get("trust", {"confidence": data.get("confidence", 0.75), "last_confirmed_at": None, "conflict_count": 0}),
        "lifecycle_state": lifecycle_state,
        "user_flags": data.get("user_flags", {"pinned": False, "quiet": False, "ephemeral": False, "require_confirm": False}),
        "sensitivity": data.get("sensitivity", {"level": "none", "pii_types": []}),
        "decay_half_life": data.get("decay_half_life", 60),  # days
        "last_accessed_at": now,
        "created_at": now,
        "updated_at": now,
    "model_version": data.get("model_version", settings.EMBEDDING_MODEL_VERSION),
        "lineage": data.get("lineage", {}),
        "conflict_with": str(conflict_with.get("_id")) if conflict_with else None,
    }

    inserted_id = coll.insert_one(doc).inserted_id
    doc["_id"] = str(inserted_id)
    # Upsert embedding (title + value composite)
    try:
        embed_text = f"{title}: {doc.get('value','')}"
        upsert_memory_embedding(doc["_id"], user_id, embed_text, doc.get("lifecycle_state", "active"))
    except Exception:
        pass
    return doc


async def list_memories(
    user_id: str,
    limit: int = 200,
    lifecycle: Optional[List[str]] = None,
    include_distilled: bool = True,
    originals_only: bool = False,
) -> List[Dict[str, Any]]:
    coll = get_memories_collection()
    q: Dict[str, Any] = {"user_id": user_id}
    if lifecycle:
        q["lifecycle_state"] = {"$in": lifecycle}
    if not include_distilled:
        q["type"] = {"$ne": "distilled"}
    if originals_only:
        # exclude any memory that has been distilled (i.e., has lineage.distilled_id set) but is not itself distilled
        q["lineage.distilled_id"] = {"$exists": False}
    cur = coll.find(q).sort("updated_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    for d in cur:
        d["_id"] = str(d["_id"])  # type: ignore
        out.append(d)
    return out


async def get_memory(user_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
    coll = get_memories_collection()
    d = coll.find_one({"_id": _coerce_object_id(memory_id), "user_id": user_id})
    if not d:
        return None
    d["_id"] = str(d["_id"])  # type: ignore
    return d


async def _snapshot_version(original: Dict[str, Any], reason: str = "update") -> None:
    vcoll = get_memory_versions_collection()
    snap = {
        "memory_id": str(original.get("_id")),
        "snapshot": {
            "value": original.get("value"),
            "structured_value": original.get("structured_value"),
            "trust": original.get("trust"),
        },
        "changed_at": _now_iso(),
        "change_reason": reason,
    }
    try:
        vcoll.insert_one(snap)
    except Exception:
        pass


async def update_memory(user_id: str, memory_id: str, patch: Dict[str, Any], reason: str = "update") -> Optional[Dict[str, Any]]:
    coll = get_memories_collection()
    existing = coll.find_one({"_id": _coerce_object_id(memory_id), "user_id": user_id})
    if not existing:
        return None

    await _snapshot_version(existing, reason=reason)

    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    allowed_fields = {
        "value",
        "structured_value",
        "priority",
        "salience_score",
        "trust",
        "lifecycle_state",
        "user_flags",
        "sensitivity",
        "decay_half_life",
        "lineage",
    }
    for k, v in patch.items():
        if k in allowed_fields:
            updates[k] = v
    coll.update_one({"_id": existing["_id"]}, {"$set": updates})
    new_doc = coll.find_one({"_id": existing["_id"]})
    if new_doc:
        new_doc["_id"] = str(new_doc["_id"])  # type: ignore
        try:
            embed_text = f"{new_doc.get('title')}: {new_doc.get('value','')}"
            upsert_memory_embedding(new_doc["_id"], user_id, embed_text, new_doc.get("lifecycle_state", "active"))
            coll.update_one({"_id": new_doc["_id"]}, {"$set": {"model_version": settings.EMBEDDING_MODEL_VERSION}})
        except Exception:
            pass
    return new_doc


async def confirm_memory(user_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
    """Promote a candidate memory to active, setting last_confirmed_at."""
    coll = get_memories_collection()
    existing = coll.find_one({"_id": _coerce_object_id(memory_id), "user_id": user_id})
    if not existing:
        return None
    if existing.get("lifecycle_state") != "active":
        last_conf = _now_iso()
        coll.update_one({"_id": existing["_id"]}, {"$set": {"lifecycle_state": "active", "trust.last_confirmed_at": last_conf}})
    updated = coll.find_one({"_id": existing["_id"]})
    if updated:
        updated["_id"] = str(updated["_id"])  # type: ignore
    return updated


def log_pii_block(user_id: str, memory_id: str | None, trigger_text: str, rule: str, sensitivity_level: str | None):
    """Synchronous best-effort log for blocked sensitive memory reference."""
    try:
        coll = get_pii_audit_collection()
        coll.insert_one({
            "user_id": user_id,
            "memory_id": memory_id,
            "trigger_text": trigger_text[:500],
            "rule": rule,
            "sensitivity_level": sensitivity_level,
            "created_at": _now_iso(),
        })
    except Exception:  # noqa: BLE001
        pass


async def restore_memory(user_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
    """Restore an archived memory to active if within undo window."""
    coll = get_memories_collection()
    existing = coll.find_one({"_id": _coerce_object_id(memory_id), "user_id": user_id})
    if not existing:
        return None
    if existing.get("lifecycle_state") != "archived":
        return None
    undo_expiry = existing.get("undo_expiry_at")
    try:
        if undo_expiry and datetime.fromisoformat(undo_expiry.replace("Z", "")) < datetime.utcnow():
            return None
    except Exception:
        pass
    # Snapshot
    await _snapshot_version(existing, reason="restore")
    coll.update_one({"_id": existing["_id"]}, {"$set": {"lifecycle_state": "active", "updated_at": _now_iso(), "archived_at": None}})
    doc = coll.find_one({"_id": existing["_id"]})
    if doc:
        doc["_id"] = str(doc["_id"])  # type: ignore
    return doc


async def log_recall_event(user_id: str, query_text: str, scores: List[Dict[str, Any]], accepted: Optional[bool] = None) -> str:
    rcoll = get_recall_events_collection()
    # For analytics we derive quick-access arrays for distribution queries without unwinding deeply each time.
    # Store parallel arrays of score and similarity plus simple aggregates.
    score_values = [s.get("score", 0.0) for s in scores]
    similarity_values = [s.get("similarity", 0.0) for s in scores]
    priorities = [s.get("priority") for s in scores]
    saliences = [s.get("salience") for s in scores]
    doc = {
        "user_id": user_id,
        "query_text": query_text,
        "scores": scores,  # full per-memory breakdown
        "accepted": accepted,  # later updated after user feedback (True=helpful, False=incorrect)
        "responded_at": _now_iso(),
        # Analytics convenience fields
        "score_values": score_values,
        "similarity_values": similarity_values,
        "avg_score": (sum(score_values) / len(score_values)) if score_values else 0.0,
        "top_score": max(score_values) if score_values else 0.0,
        "avg_similarity": (sum(similarity_values) / len(similarity_values)) if similarity_values else 0.0,
        "top_similarity": max(similarity_values) if similarity_values else 0.0,
        "priorities": priorities,
        "saliences": saliences,
        "num_candidates": len(scores),
    }
    inserted = rcoll.insert_one(doc).inserted_id
    return str(inserted)


async def update_recall_event_feedback(event_id: str, user_id: str, accepted: bool | None = None, correction: bool | None = None) -> bool:
    """Update a recall event after explicit user feedback.

    accepted: user indicated memory injections were helpful.
    correction: user indicated at least one injected memory was wrong / not relevant (sets accepted False if provided).
    """
    rcoll = get_recall_events_collection()
    oid = None
    try:
        oid = _coerce_object_id(event_id)
    except Exception:
        return False
    update: Dict[str, Any] = {"feedback_at": _now_iso()}
    if accepted is not None:
        update["accepted"] = bool(accepted)
    if correction:
        update["accepted"] = False
        update["correction_flag"] = True
    res = rcoll.update_one({"_id": oid, "user_id": user_id}, {"$set": update})
    return res.modified_count == 1


async def aggregate_recall_histogram(user_id: str, bins: int = 12, score_min: float | None = None, score_max: float | None = None) -> Dict[str, Any]:
    """Compute a histogram of top scores with acceptance split.

    We consider the top_score from each recall event as the representative retrieval strength for that query.
    Returns bin edges, counts_total, counts_accepted, counts_rejected.
    """
    rcoll = get_recall_events_collection()
    # Determine dynamic min/max if not provided
    match_stage = {"user_id": user_id, "top_score": {"$gt": 0}}
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": None, "min": {"$min": "$top_score"}, "max": {"$max": "$top_score"}, "count": {"$sum": 1}}},
    ]
    stats = list(rcoll.aggregate(pipeline))
    if not stats or stats[0].get("count", 0) == 0:
        return {"bins": [], "counts_total": [], "counts_accepted": [], "counts_rejected": [], "total_events": 0}
    stat = stats[0]
    _min = float(score_min if score_min is not None else stat.get("min", 0.0))
    _max = float(score_max if score_max is not None else stat.get("max", 0.0))
    if _max <= _min:
        _max = _min + 1e-6
    width = (_max - _min) / bins
    edges = [_min + i * width for i in range(bins + 1)]
    # Classification into bins using $bucketAuto would ignore explicit edges; we manually map.
    events = list(rcoll.find({"user_id": user_id}, {"top_score": 1, "accepted": 1}))
    total = [0] * bins
    acc = [0] * bins
    rej = [0] * bins
    for ev in events:
        ts = float(ev.get("top_score", 0.0))
        # Determine bin index
        idx = int((ts - _min) / width)
        if idx >= bins:
            idx = bins - 1
        if idx < 0:
            continue
        total[idx] += 1
        acc_flag = ev.get("accepted")
        if acc_flag is True:
            acc[idx] += 1
        elif acc_flag is False:
            rej[idx] += 1
    return {
        "bins": edges,
        "counts_total": total,
        "counts_accepted": acc,
        "counts_rejected": rej,
        "total_events": len(events),
        "range": {"min": _min, "max": _max},
    }


async def touch_memory_access(user_id: str, memory_ids: List[str]) -> None:
    if not memory_ids:
        return
    coll = get_memories_collection()
    now = _now_iso()
    try:
        coll.update_many({"user_id": user_id, "_id": {"$in": [ObjectId(m) for m in memory_ids]}}, {"$set": {"last_accessed_at": now}})
    except Exception:
        pass


# Simple placeholder weighting - not yet used; kept for clarity
async def score_memory_for_query(memory: Dict[str, Any]) -> float:
    # Placeholder; actual scoring done in retrieval coordinator (future)
    base = 1.0
    priority = memory.get("priority", DEFAULT_PRIORITY)
    base *= PRIORITY_WEIGHTS.get(priority, 1.0)
    return base


# -----------------------------
# Distillation Support
# -----------------------------

async def get_distillation_candidates(user_id: str, limit: int = 50, min_age_days: int = 45, max_salience: float = 0.93) -> List[Dict[str, Any]]:
    """Return low-salience, aging/archived memories not already distilled.

    Heuristics (initial):
      - lifecycle_state in {aging, archived}
      - salience_score <= max_salience
      - last_accessed_at older than min_age_days
      - not pinned, not already with lineage.distilled_id
    """
    coll = get_memories_collection()
    now = datetime.utcnow()
    cutoff = (now.replace(microsecond=0) - __import__('datetime').timedelta(days=min_age_days)).isoformat()
    q = {
        "user_id": user_id,
        "lifecycle_state": {"$in": ["aging", "archived"]},
        "salience_score": {"$lte": max_salience},
        "last_accessed_at": {"$lt": cutoff},
        "user_flags.pinned": {"$ne": True},
        "lineage.distilled_id": {"$exists": False},
        "type": {"$ne": "distilled"},
    }
    cur = coll.find(q).sort("salience_score", 1).limit(limit)
    out: List[Dict[str, Any]] = []
    for d in cur:
        d["_id"] = str(d["_id"])  # type: ignore
        out.append(d)
    return out


async def run_distillation_batch(user_id: str, candidate_ids: List[str], summary_model: str | None = None) -> Dict[str, Any]:
    """Create a distilled summary memory from selected low-value originals.

    Placeholder summarization: concatenates titles + truncated values; future: call LLM summarizer.
    Ensures idempotency by checking if all originals already point to the same distilled_id.
    """
    if not candidate_ids:
        return {"created": False, "reason": "no_candidates"}
    coll = get_memories_collection()
    oids = []
    for cid in candidate_ids:
        try:
            oids.append(_coerce_object_id(cid))
        except Exception:
            continue
    originals = list(coll.find({"_id": {"$in": oids}, "user_id": user_id}))
    if not originals:
        return {"created": False, "reason": "not_found"}
    # Check idempotency: if all have same lineage.distilled_id -> return that
    distilled_ids = {str(o.get("lineage", {}).get("distilled_id")) for o in originals if o.get("lineage", {}).get("distilled_id")}
    if len(distilled_ids) == 1:
        return {"created": False, "reason": "already_distilled", "distilled_id": list(distilled_ids)[0]}
    # Advanced hierarchical summarization
    summary_text = ""
    original_items = []
    for o in originals:
        original_items.append({
            "title": o.get("title") or "(untitled)",
            "value": (o.get("value") or "").strip(),
        })
    try:
        from app.services.ai_service import structured_distillation_summary
        summary_text = structured_distillation_summary(original_items, char_limit=1500)
    except Exception:
        summary_text = ""
    if not summary_text:
        # Minimal fallback: join titles
        summary_text = ", ".join(i.get("title") for i in original_items)[:1500]
    # Enforce max length
    if len(summary_text) > 1500:
        summary_text = summary_text[:1497] + "..."
    doc = {
        "user_id": user_id,
        "title": f"Distilled summary ({len(originals)} memories)",
        "type": "distilled",
        "value": summary_text,
        "priority": "low",
        "salience_score": 0.88,  # starting midpoint; will adapt with usage
        "trust": {"confidence": 0.7, "last_confirmed_at": None, "conflict_count": 0},
        "lifecycle_state": "active",  # make active so it can be retrieved
        "user_flags": {"pinned": False, "quiet": False, "ephemeral": False, "require_confirm": False},
        "sensitivity": {"level": "none", "pii_types": []},
        "decay_half_life": 90,
        "last_accessed_at": _now_iso(),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "model_version": settings.EMBEDDING_MODEL_VERSION,
        "lineage": {"original_ids": [str(o.get("_id")) for o in originals]},
    }
    inserted_id = coll.insert_one(doc).inserted_id
    distilled_id = str(inserted_id)
    # Upsert embedding best-effort
    try:
        upsert_memory_embedding(distilled_id, user_id, summary_text, doc.get("lifecycle_state", "active"))
    except Exception:
        pass
    # Update originals lineage + archive them (if not already)
    for o in originals:
        try:
            update_fields = {"lineage.distilled_id": distilled_id, "updated_at": _now_iso()}
            if o.get("lifecycle_state") != "archived":
                update_fields["lifecycle_state"] = "archived"
                update_fields["archived_at"] = _now_iso()
            coll.update_one({"_id": o["_id"]}, {"$set": update_fields})
        except Exception:
            continue
    return {"created": True, "distilled_id": distilled_id, "original_count": len(originals)}


async def get_lineage(memory_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    coll = get_memories_collection()
    try:
        oid = _coerce_object_id(memory_id)
    except Exception:
        return None
    doc = coll.find_one({"_id": oid, "user_id": user_id})
    if not doc:
        return None
    # Expand lineage references
    lineage = doc.get("lineage", {}) or {}
    originals: List[Dict[str, Any]] = []
    distilled: Optional[Dict[str, Any]] = None
    if doc.get("type") == "distilled":
        # fetch originals
        oids = [ _coerce_object_id(i) for i in lineage.get("original_ids", []) if i ]
        if oids:
            for o in coll.find({"_id": {"$in": oids}}):
                o["_id"] = str(o["_id"])  # type: ignore
                originals.append(o)
        doc["_id"] = str(doc["_id"])  # type: ignore
        return {"distilled": doc, "originals": originals}
    else:
        # original memory: maybe has distilled_id
        d_id = lineage.get("distilled_id")
        if d_id:
            try:
                d_doc = coll.find_one({"_id": _coerce_object_id(d_id)})
                if d_doc:
                    d_doc["_id"] = str(d_doc["_id"])  # type: ignore
                    distilled = d_doc
            except Exception:
                pass
        doc["_id"] = str(doc["_id"])  # type: ignore
        return {"original": doc, "distilled": distilled}


# -----------------------------
# Analytics Helpers (Dashboard)
# -----------------------------
async def gating_trend(user_id: str, window_days: int = 14) -> Dict[str, Any]:
    """Produce per-day gating stats within a lookback window.

    Returns dict with arrays: dates, gated, injected, gating_rate, near_miss_salience, near_miss_trust, near_miss_composite.
    """
    from datetime import datetime, timedelta
    coll = get_recall_events_collection()
    now = datetime.utcnow()
    start = (now - timedelta(days=window_days))
    # Fetch events in window (limit safety)
    cur = coll.find({
        "user_id": user_id,
        "responded_at": {"$gte": start.isoformat()}
    }).sort("responded_at", -1).limit(5000)
    # Bucket by date string
    buckets: Dict[str, Dict[str, int]] = {}
    from app.config import settings as _settings
    gate_enabled = getattr(_settings, "MEMORY_GATE_ENABLE", True)
    thr_sal = getattr(_settings, "MEMORY_GATE_MIN_SALIENCE", 0.85)
    thr_trust = getattr(_settings, "MEMORY_GATE_MIN_TRUST", 0.55)
    thr_comp = getattr(_settings, "MEMORY_GATE_MIN_COMPOSITE", 0.35)
    if not gate_enabled:
        return {"dates": [], "gated": [], "injected": [], "gating_rate": [], "near_miss_salience": [], "near_miss_trust": [], "near_miss_composite": []}
    for ev in cur:
        ts_raw = ev.get("responded_at")
        try:
            dt = datetime.fromisoformat(str(ts_raw).replace("Z", ""))
        except Exception:
            continue
        if dt < start:
            continue
        day_key = dt.strftime("%Y-%m-%d")
        b = buckets.setdefault(day_key, {"gated": 0, "injected": 0, "near_sal": 0, "near_trust": 0, "near_comp": 0})
        scores = ev.get("scores") or []
        for s in scores:
            if s.get("gated") is True:
                b["gated"] += 1
                # derive trust_conf from trust_factor
                trust_factor = s.get("trust_factor")
                trust_conf = None
                try:
                    if trust_factor is not None:
                        trust_conf = (float(trust_factor) - 0.8) / 0.2
                except Exception:
                    trust_conf = None
                sal = s.get("salience") or 0.0
                sim = s.get("similarity") or 0.0
                comp = sim * sal * (trust_conf if trust_conf is not None else 0.75)
                if thr_sal - 0.03 <= sal < thr_sal:
                    b["near_sal"] += 1
                if trust_conf is not None and thr_trust - 0.05 <= trust_conf < thr_trust:
                    b["near_trust"] += 1
                if thr_comp - 0.03 <= comp < thr_comp:
                    b["near_comp"] += 1
            else:
                # If explicitly gated False, treat as injected candidate (not all may be finally used but candidate pool)
                b["injected"] += 1
    # Ensure chronological order
    dates_sorted = sorted(buckets.keys())
    gated_arr = [buckets[d]["gated"] for d in dates_sorted]
    injected_arr = [buckets[d]["injected"] for d in dates_sorted]
    rate_arr = []
    for g, inj in zip(gated_arr, injected_arr):
        total = g + inj
        rate_arr.append(g / total if total else 0.0)
    return {
        "dates": dates_sorted,
        "gated": gated_arr,
        "injected": injected_arr,
        "gating_rate": rate_arr,
        "near_miss_salience": [buckets[d]["near_sal"] for d in dates_sorted],
        "near_miss_trust": [buckets[d]["near_trust"] for d in dates_sorted],
        "near_miss_composite": [buckets[d]["near_comp"] for d in dates_sorted],
    }
