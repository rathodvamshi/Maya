"""Prometheus metrics for emotion subsystem.

Exposed automatically if Prometheus integration already scrapes /metrics via
existing middleware or a dedicated endpoint elsewhere.
"""
from __future__ import annotations
from prometheus_client import Counter, Histogram, Gauge

EMOTION_REQ_COUNTER = Counter(
    "emotion_requests_total",
    "Total emotion analyze requests",
    labelnames=("path","advanced","triggered")
)

EMOTION_LATENCY_HIST = Histogram(
    "emotion_latency_seconds",
    "Latency for advanced emotion analysis",
    buckets=(0.005,0.01,0.02,0.05,0.1,0.25,0.5,1.0)
)

EMOJI_APPEND_COUNTER = Counter(
    "emoji_appends_total",
    "Count of times an emoji was suggested/appended by advanced analyzer",
    labelnames=("emotion","style")
)

__all__ = [
    "EMOTION_REQ_COUNTER",
    "EMOTION_LATENCY_HIST",
    "EMOJI_APPEND_COUNTER",
]

# -----------------------------
# Pipeline & API Prometheus metrics (for Grafana/Prometheus dashboards)
# -----------------------------

PIPELINE_STAGE_LATENCY = Histogram(
    "pipeline_stage_latency_seconds",
    "Latency per pipeline stage",
    labelnames=("stage",),
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0),
)

API_REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "API requests labeled by status",
    labelnames=("status",),
)

TASK_COMPLETION_TOTAL = Counter(
    "task_completion_total",
    "Number of tasks completed",
)

def record_pipeline_stage(stage: str, ms: float) -> None:
    try:
        PIPELINE_STAGE_LATENCY.labels(stage=stage).observe(max(0.0, float(ms) / 1000.0))
    except Exception:
        pass


__all__ += [
    "PIPELINE_STAGE_LATENCY",
    "API_REQUESTS_TOTAL",
    "TASK_COMPLETION_TOTAL",
    "record_pipeline_stage",
]

# -----------------------------
# Realtime (SSE) metrics
# -----------------------------

REALTIME_EVENTS_EMITTED = Counter(
    "realtime_events_emitted_total",
    "Total realtime events emitted",
    labelnames=("type",),
)

REALTIME_EVENTS_DROPPED = Counter(
    "realtime_events_dropped_total",
    "Total realtime events dropped (e.g., backpressure)",
    labelnames=("reason",),
)

REALTIME_SSE_CONNECTIONS = Gauge(
    "realtime_sse_connections",
    "Number of active SSE connections",
)

__all__ += [
    "REALTIME_EVENTS_EMITTED",
    "REALTIME_EVENTS_DROPPED",
    "REALTIME_SSE_CONNECTIONS",
]
