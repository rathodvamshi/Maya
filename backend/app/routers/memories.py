from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pymongo.collection import Collection
from bson import ObjectId
from datetime import datetime
import io, json, zipfile

from app.security import get_current_active_user
from app.database import get_sessions_collection
from app.services.neo4j_service import neo4j_service
from app.services import pinecone_service, redis_service
from app.services import memory_service
from app.database import get_recall_events_collection, get_memories_collection
from app.database import get_pii_audit_collection
from app.config import settings
from app.celery_tasks import process_and_store_memory

router = APIRouter(prefix="/api/memories", tags=["Memories"], dependencies=[Depends(get_current_active_user)])


@router.get("/", summary="List user long-term memories")
async def list_user_memories(
    limit: int = 200,
    lifecycle: str | None = None,
    include_distilled: bool = True,
    originals_only: bool = False,
    current_user: dict = Depends(get_current_active_user),
):
    lifecycles = lifecycle.split(",") if lifecycle else None
    docs = await memory_service.list_memories(
        str(current_user["_id"]),
        limit=limit,
        lifecycle=lifecycles,
        include_distilled=include_distilled,
        originals_only=originals_only,
    )
    return {"items": docs, "count": len(docs)}


@router.post("/create", summary="Create a new memory item")
async def create_memory(payload: dict, sync: bool = False, current_user: dict = Depends(get_current_active_user)):
    try:
        payload["user_id"] = str(current_user["_id"])
        doc = await memory_service.create_memory(payload)
        # Process embedding + pinecone + neo4j
        text = f"{doc.get('title')}: {doc.get('value','')}"
        if sync:
            # Run inline for deterministic behavior when broker/worker aren’t available
            try:
                res = process_and_store_memory.apply(args=[payload["user_id"], doc["_id"], text, doc.get("source_type", "user")]).get(timeout=60)
                return {"status": "processed", "result": res, "memory": doc}
            except Exception:
                # Still return created doc if inline processing fails
                return doc
        else:
            try:
                task = process_and_store_memory.delay(
                    user_id=payload["user_id"],
                    memory_id=doc["_id"],
                    text=text,
                    source=doc.get("source_type", "user"),
                )
                # Return 202 with task id to allow frontend to poll
                return {"status": "accepted", "task_id": getattr(task, 'id', None), "memory": doc}
            except Exception:
                # Fallback: run inline if queueing failed
                try:
                    res = process_and_store_memory.apply(args=[payload["user_id"], doc["_id"], text, doc.get("source_type", "user")]).get(timeout=60)
                    return {"status": "processed", "result": res, "memory": doc}
                except Exception:
                    return doc
    except ValueError as ve:  # validation
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="create_failed") from e


@router.get("/{memory_id}", summary="Get a single memory")
async def get_memory(memory_id: str, current_user: dict = Depends(get_current_active_user)):
    doc = await memory_service.get_memory(str(current_user["_id"]), memory_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not_found")
    return doc


@router.patch("/{memory_id}", summary="Update a memory (versioned)")
async def update_memory(memory_id: str, patch: dict, current_user: dict = Depends(get_current_active_user)):
    updated = await memory_service.update_memory(str(current_user["_id"]), memory_id, patch, reason=patch.get("reason", "update"))
    if not updated:
        raise HTTPException(status_code=404, detail="not_found")
    return updated


@router.post("/{memory_id}/reprocess", summary="Re-run memory pipeline for an existing memory")
async def reprocess_memory(memory_id: str, sync: bool = True, current_user: dict = Depends(get_current_active_user)):
    doc = await memory_service.get_memory(str(current_user["_id"]), memory_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not_found")
    text = f"{doc.get('title')}: {doc.get('value','')}"
    user_id = str(current_user["_id"])
    if sync:
        try:
            res = process_and_store_memory.apply(args=[user_id, memory_id, text, doc.get("source_type", "user")]).get(timeout=60)
            return {"status": "processed", "result": res}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"reprocess_failed: {e}")
    else:
        try:
            task = process_and_store_memory.delay(user_id=user_id, memory_id=memory_id, text=text, source=doc.get("source_type", "user"))
            return {"status": "accepted", "task_id": getattr(task, 'id', None)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"queue_failed: {e}")


@router.post("/{memory_id}/confirm", summary="Confirm candidate memory and promote to active")
async def confirm_memory(memory_id: str, current_user: dict = Depends(get_current_active_user)):
    confirmed = await memory_service.confirm_memory(str(current_user["_id"]), memory_id)
    if not confirmed:
        raise HTTPException(status_code=404, detail="not_found")
    return confirmed


@router.get("/recall_events", summary="List recent recall events with scoring factors")
async def list_recall_events(limit: int = 50, current_user: dict = Depends(get_current_active_user), recall_events=Depends(get_recall_events_collection)):
    cur = recall_events.find({"user_id": str(current_user["_id"])}).sort("responded_at", -1).limit(limit)
    out = []
    for d in cur:
        d["_id"] = str(d["_id"])  # type: ignore
        # Create user-friendly rationale text per memory reference if scores present
        rationale = []
        for sc in d.get("scores", []):
            try:
                sim = sc.get("similarity")
                rec = sc.get("recency_days")
                freq = sc.get("frequency", 0)
                pri = sc.get("priority")
                parts = []
                if sim is not None:
                    parts.append(f"sim {sim:.2f}")
                if rec is not None:
                    parts.append(f"recent {rec}d")
                if freq:
                    parts.append(f"{freq} mentions")
                if pri and pri != "normal":
                    parts.append(pri)
                sc["rationale_text"] = ", ".join(parts)
            except Exception:
                continue
        out.append(d)
    return {"items": out, "count": len(out)}


@router.post("/recall_events/{event_id}/feedback", summary="Update recall event feedback (accepted / correction)")
async def recall_event_feedback(event_id: str, payload: dict, current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    accepted = payload.get("accepted")
    correction = payload.get("correction")
    ok = await memory_service.update_recall_event_feedback(event_id, user_id, accepted=accepted, correction=correction)
    if not ok:
        raise HTTPException(status_code=404, detail="event_not_found")
    return {"status": "updated"}


@router.get("/recall_events/histogram", summary="Histogram analytics of recall top scores with acceptance split")
async def recall_histogram(bins: int = 12, score_min: float | None = None, score_max: float | None = None, current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    data = await memory_service.aggregate_recall_histogram(user_id, bins=bins, score_min=score_min, score_max=score_max)
    # Derive acceptance rate per non-empty bin for quick UI plotting convenience
    acceptance_rates = []
    for t, a in zip(data.get("counts_total", []), data.get("counts_accepted", [])):
        if t:
            acceptance_rates.append(a / t)
        else:
            acceptance_rates.append(None)
    data["acceptance_rates"] = acceptance_rates
    # Percentiles on top_score distribution
    from statistics import quantiles
    try:
        # Reconstruct raw values by approximating each bin's midpoint repeated count times
        vals = []
        bins_edges = data.get("bins") or []
        totals = data.get("counts_total") or []
        for i, cnt in enumerate(totals):
            if not cnt:
                continue
            if i + 1 < len(bins_edges):
                midpoint = (bins_edges[i] + bins_edges[i+1]) / 2.0
            else:
                midpoint = bins_edges[i]
            vals.extend([midpoint] * cnt)
        if len(vals) >= 5:
            qs = quantiles(vals, n=100)
            data["percentiles"] = {
                "p50": qs[49],
                "p75": qs[74],
                "p90": qs[89],
            }
    except Exception:
        pass
    return data


@router.get("/analytics/overview", summary="Memory retrieval analytics overview (acceptance, percentiles, distillation counts, correlation)")
async def memory_analytics_overview(current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    # Fetch recent recall events (cap 1000) for correlation approximations
    recall_events = get_recall_events_collection()
    cur = recall_events.find({"user_id": user_id}, {"top_score": 1, "accepted": 1, "scores": 1}).sort("responded_at", -1).limit(1000)
    top_scores = []
    accepted_flags = []
    sim_acc_pairs = []  # (similarity, accepted?)
    total = 0
    accepted_cnt = 0
    # Gating stats accumulators
    gating_evaluated = 0
    gated_count = 0
    reason_salience = 0
    reason_trust = 0
    reason_composite = 0
    near_miss_salience = 0
    near_miss_trust = 0
    near_miss_composite = 0
    from app.config import settings as _settings
    thr_sal = getattr(_settings, "MEMORY_GATE_MIN_SALIENCE", 0.85)
    thr_trust = getattr(_settings, "MEMORY_GATE_MIN_TRUST", 0.55)
    thr_comp = getattr(_settings, "MEMORY_GATE_MIN_COMPOSITE", 0.35)
    gate_enabled = getattr(_settings, "MEMORY_GATE_ENABLE", True)
    for ev in cur:
        total += 1
        ts = float(ev.get("top_score", 0.0))
        top_scores.append(ts)
        acc = ev.get("accepted")
        if acc is True:
            accepted_cnt += 1
        accepted_flags.append(1 if acc is True else 0 if acc is False else None)
        # correlation: pull highest similarity from scores if available
        try:
            scs = ev.get("scores") or []
            if scs:
                max_sim = max((s.get("similarity") or 0.0) for s in scs)
                if acc is not None:
                    sim_acc_pairs.append((float(max_sim), 1.0 if acc is True else 0.0))
            # Gating analysis per score item
            if gate_enabled and scs:
                for s in scs:
                    # All evaluated candidates appear in scores
                    gating_evaluated += 1
                    if s.get("gated") is True:
                        gated_count += 1
                        sal = s.get("salience", 0.0) or 0.0
                        trust_factor = s.get("trust_factor")
                        # back-calc confidence: trust_factor = 0.8 + 0.2 * conf
                        trust_conf = None
                        try:
                            if trust_factor is not None:
                                trust_conf = (float(trust_factor) - 0.8) / 0.2
                        except Exception:
                            trust_conf = None
                        sim = s.get("similarity", 0.0) or 0.0
                        comp = sim * sal * (trust_conf if trust_conf is not None else 0.75)
                        # Reasons (count all triggers)
                        if sal < thr_sal:
                            reason_salience += 1
                        if trust_conf is not None and trust_conf < thr_trust:
                            reason_trust += 1
                        if comp < thr_comp:
                            reason_composite += 1
                        # Near-miss windows: within small deltas
                        if thr_sal - 0.03 <= sal < thr_sal:
                            near_miss_salience += 1
                        if trust_conf is not None and thr_trust - 0.05 <= trust_conf < thr_trust:
                            near_miss_trust += 1
                        if thr_comp - 0.03 <= comp < thr_comp:
                            near_miss_composite += 1
        except Exception:
            continue
    overview = {"total_events": total}
    if total:
        overview["acceptance_rate"] = accepted_cnt / total
    # Percentiles of top_scores
    try:
        from statistics import quantiles
        if len(top_scores) >= 5:
            qs = quantiles(sorted(top_scores), n=100)
            overview["score_percentiles"] = {"p50": qs[49], "p75": qs[74], "p90": qs[89]}
    except Exception:
        pass
    # Distillation counts
    mem_coll = get_memories_collection()
    total_original = mem_coll.count_documents({"user_id": user_id, "type": {"$ne": "distilled"}})
    total_distilled = mem_coll.count_documents({"user_id": user_id, "type": "distilled"})
    overview["distillation"] = {
        "original": total_original,
        "distilled": total_distilled,
        "ratio_distilled": (total_distilled / total_original) if total_original else 0.0,
    }
    # Correlation (Pearson) between similarity and acceptance
    def _pearson(pairs):
        if len(pairs) < 3:
            return None
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mean_x = sum(xs)/len(xs)
        mean_y = sum(ys)/len(ys)
        num = sum((x-mean_x)*(y-mean_y) for x,y in pairs)
        den_x = (sum((x-mean_x)**2 for x in xs))**0.5
        den_y = (sum((y-mean_y)**2 for y in ys))**0.5
        if not den_x or not den_y:
            return None
        return num/(den_x*den_y)
    overview["similarity_acceptance_correlation"] = _pearson(sim_acc_pairs)
    # Inject gating stats
    if gate_enabled and gating_evaluated:
        overview["gating"] = {
            "evaluated": gating_evaluated,
            "gated": gated_count,
            "injected": gating_evaluated - gated_count,
            "gating_rate": gated_count / gating_evaluated if gating_evaluated else 0.0,
            "reasons": {
                "salience_below": reason_salience,
                "trust_below": reason_trust,
                "composite_below": reason_composite,
            },
            "near_miss": {
                "salience": near_miss_salience,
                "trust": near_miss_trust,
                "composite": near_miss_composite,
            },
            "thresholds": {
                "min_salience": thr_sal,
                "min_trust": thr_trust,
                "min_composite": thr_comp,
            },
        }
    return overview


@router.get("/analytics/dashboard", summary="Unified dashboard JSON spec for frontend charts")
async def analytics_dashboard(
    bins: int = 15,
    window_days: int = 14,
    include_histogram: bool = True,
    include_gating_trend: bool = True,
    include_overview: bool = True,
    current_user: dict = Depends(get_current_active_user),
):
    """Return a structured JSON bundle with metrics + chart specs for a frontend.

    This avoids the frontend hard-coding transformation logic and supports drop-in chart wiring.
    """
    user_id = str(current_user["_id"])
    bundle: Dict[str, Any] = {"user_id": user_id, "generated_at": __import__('datetime').datetime.utcnow().isoformat()}
    # Overview
    if include_overview:
        bundle["overview"] = await memory_analytics_overview(current_user)  # reuse handler
    # Histogram (score distribution)
    if include_histogram:
        bundle["histogram"] = await recall_histogram(bins=bins, current_user=current_user)
    # Gating trend
    if include_gating_trend:
        from app.services.memory_service import gating_trend
        bundle["gating_trend"] = await gating_trend(user_id, window_days=window_days)
    # Chart specs (lightweight Vega-lite inspired metadata)
    charts: List[Dict[str, Any]] = []
    if "histogram" in bundle:
        charts.append({
            "id": "recall_score_histogram",
            "title": "Recall Score Distribution",
            "type": "bar-overlay",
            "x": {"field": "bins", "type": "quantitative", "description": "Score bins"},
            "series": [
                {"field": "counts_total", "label": "Total", "color": "#6B7280"},
                {"field": "counts_accepted", "label": "Accepted", "color": "#10B981"},
                {"field": "counts_rejected", "label": "Rejected", "color": "#EF4444"},
            ],
            "overlay_line": {"field": "acceptance_rates", "label": "Acceptance Rate", "color": "#3B82F6"},
        })
    if "overview" in bundle:
        ov = bundle["overview"]
        if ov.get("score_percentiles"):
            charts.append({
                "id": "score_percentiles",
                "title": "Score Percentiles",
                "type": "stat-cards",
                "cards": [
                    {"label": "p50", "value": round(ov["score_percentiles"]["p50"], 4)},
                    {"label": "p75", "value": round(ov["score_percentiles"]["p75"], 4)},
                    {"label": "p90", "value": round(ov["score_percentiles"]["p90"], 4)},
                ],
            })
        if ov.get("gating"):
            g = ov["gating"]
            charts.append({
                "id": "gating_summary",
                "title": "Gating Summary",
                "type": "summary-table",
                "rows": [
                    {"label": "Evaluated", "value": g.get("evaluated")},
                    {"label": "Gated", "value": g.get("gated")},
                    {"label": "Injected", "value": g.get("injected")},
                    {"label": "Gating Rate", "value": round(g.get("gating_rate", 0.0), 4)},
                ],
            })
    if "gating_trend" in bundle:
        charts.append({
            "id": "gating_trend",
            "title": "Gating Rate & Near-Miss Trend",
            "type": "multi-axis",
            "x": {"field": "dates", "type": "temporal"},
            "y_primary": {"field": "gating_rate", "label": "Gating Rate", "type": "quantitative"},
            "y_secondary": [
                {"field": "near_miss_salience", "label": "Near Salience", "color": "#F59E0B"},
                {"field": "near_miss_trust", "label": "Near Trust", "color": "#6366F1"},
                {"field": "near_miss_composite", "label": "Near Composite", "color": "#EC4899"},
            ],
        })
    # Distillation ratio chart if available
    if bundle.get("overview", {}).get("distillation"):
        dist = bundle["overview"]["distillation"]
        charts.append({
            "id": "distillation_ratio",
            "title": "Distillation Ratio",
            "type": "donut",
            "segments": [
                {"label": "Original", "value": dist.get("original")},
                {"label": "Distilled", "value": dist.get("distilled")},
            ],
            "meta": {"ratio": dist.get("ratio_distilled")},
        })
    bundle["charts"] = charts
    # Documentation / schema metadata
    bundle["schema"] = {
        "version": 1,
        "description": "Unified memory analytics dashboard payload.",
        "sections": [
            {"key": "overview", "optional": True},
            {"key": "histogram", "optional": True},
            {"key": "gating_trend", "optional": True},
            {"key": "charts", "optional": False},
        ],
    }
    return bundle


# -----------------------------
# Distillation Endpoints
# -----------------------------

@router.get("/distillation/candidates", summary="List candidate memories for distillation")
async def distillation_candidates(limit: int = 50, min_age_days: int = 45, max_salience: float = 0.93, current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    cands = await memory_service.get_distillation_candidates(user_id, limit=limit, min_age_days=min_age_days, max_salience=max_salience)
    return {"items": cands, "count": len(cands)}


@router.post("/distillation/run", summary="Run a distillation batch over supplied candidate IDs")
async def run_distillation(payload: dict, current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    ids = payload.get("candidate_ids") or []
    result = await memory_service.run_distillation_batch(user_id, ids)
    if not result.get("created") and result.get("reason") == "not_found":
        raise HTTPException(status_code=404, detail="candidates_not_found")
    return result


@router.get("/{memory_id}/lineage", summary="Get lineage (originals<->distilled) for a memory")
async def memory_lineage(memory_id: str, current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    data = await memory_service.get_lineage(memory_id, user_id)
    if not data:
        raise HTTPException(status_code=404, detail="not_found")
    return data


@router.get("/pii_audit", summary="List recent PII audit blocks")
async def list_pii_audit(limit: int = 100, current_user: dict = Depends(get_current_active_user), pii_audit=Depends(get_pii_audit_collection)):
    cur = pii_audit.find({"user_id": str(current_user["_id"])}).sort("created_at", -1).limit(limit)
    out = []
    for d in cur:
        d["_id"] = str(d["_id"])  # type: ignore
        out.append(d)
    return {"items": out, "count": len(out)}


@router.post("/{memory_id}/restore", summary="Restore an archived memory (if within undo window)")
async def restore_memory(memory_id: str, current_user: dict = Depends(get_current_active_user)):
    doc = await memory_service.restore_memory(str(current_user["_id"]), memory_id)
    if not doc:
        raise HTTPException(status_code=404, detail="restore_not_available")
    return doc


@router.post("/reembed", summary="Trigger re-embedding of outdated memories (admin/self)")
async def trigger_reembed(limit: int = 300, current_user: dict = Depends(get_current_active_user)):
    # For now allow all authenticated users to trigger their own; future: admin gate for global
    from app.celery_worker import reembed_outdated_memories
    reembed_outdated_memories.delay(batch_size=limit)
    return {"status": "queued", "target_version": settings.EMBEDDING_MODEL_VERSION, "batch_limit": limit}

@router.post("/export")
async def export_memories(current_user: dict = Depends(get_current_active_user), sessions: Collection = Depends(get_sessions_collection)):
    user_id = str(current_user["_id"])

    # Gather Mongo sessions
    cur = sessions.find({"userId": current_user["_id"]})
    sessions_data = [{"_id": str(s["_id"]), "title": s.get("title"), "messages": s.get("messages", [])} for s in cur]

    # Neo4j facts (as text bullets)
    facts = await neo4j_service.get_user_facts(user_id)

    # Pinecone metadata cannot be exported without listing; we export a placeholder
    pinecone_meta_note = "Pinecone vectors exist keyed by user_id; raw text may be omitted for privacy."

    blob = {
        "exported_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "sessions": sessions_data,
        "neo4j_facts": facts,
        "pinecone": pinecone_meta_note,
    }

    # Zip the JSON for delivery
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("memories.json", json.dumps(blob, ensure_ascii=False, indent=2))
    mem.seek(0)

    from fastapi.responses import StreamingResponse
    headers = {"Content-Disposition": "attachment; filename=memories.zip"}
    return StreamingResponse(mem, media_type="application/zip", headers=headers)


@router.delete("/{user_id}")
async def delete_memories(user_id: str, current_user: dict = Depends(get_current_active_user), sessions: Collection = Depends(get_sessions_collection)):
    # Only allow self-delete unless you have an admin flag (omitted for brevity)
    if user_id != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Delete Mongo sessions
    sessions.delete_many({"userId": current_user["_id"]})

    # Delete Redis keys (best-effort)
    try:
        if redis_service.redis_client:
            await redis_service.redis_client.delete(f"user:{user_id}:recent_profile")
    except Exception:
        pass

    # Delete Pinecone vectors by user prefix: not directly supported via prefix; require filter delete
    try:
        if pinecone_service.is_ready():
            idx = pinecone_service.get_index()
            if idx:
                idx.delete(filter={"user_id": {"$eq": user_id}})
    except Exception:
        pass

    # Delete Neo4j user node and relationships
    try:
        await neo4j_service.run_query("MATCH (u:User {id:$uid}) DETACH DELETE u", {"uid": user_id})
    except Exception:
        pass

    return {"status": "deleted"}
