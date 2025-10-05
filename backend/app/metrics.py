"""Prometheus metrics for emotion subsystem.

Exposed automatically if Prometheus integration already scrapes /metrics via
existing middleware or a dedicated endpoint elsewhere.
"""
from __future__ import annotations
from prometheus_client import Counter, Histogram

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
