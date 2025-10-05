from fastapi import APIRouter
from app.services import metrics

# Original (non /api) routes retained for backward compatibility
router = APIRouter(prefix="/metrics", tags=["Metrics"])

# Mirrored /api namespace
api_router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

def _hedge_payload():
    snap = metrics.snapshot()
    counters = snap.get("counters", {})
    gauges = snap.get("gauges", {})
    hist = snap.get("histograms", {})
    hedge_counters = {k: v for k, v in counters.items() if k.startswith("chat.hedge") or k.startswith("chat.provider.recovery")}
    provider_latency = {k: v for k, v in hist.items() if k.startswith("provider.latency.")}
    win_latency = hist.get("chat.hedge.win_latency_ms")
    return {
        "hedge_counters": hedge_counters,
        "gauges": {k: v for k, v in gauges.items() if k.startswith("chat.hedge")},
        "provider_latency_hist": provider_latency,
        "hedge_win_latency_hist": win_latency,
    }

@router.get("/hedge")
async def hedge_metrics():
    return _hedge_payload()

@api_router.get("/hedge")
async def hedge_metrics_api():  # pragma: no cover simple mirror
    return _hedge_payload()

@router.get("/all")
async def all_metrics():
    return metrics.snapshot()

@api_router.get("/all")
async def all_metrics_api():  # pragma: no cover simple mirror
    return metrics.snapshot()