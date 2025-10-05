"""Lightweight in-process metrics aggregation.

This avoids external dependencies; counters are simple integers.
Thread-safety: GIL provides basic safety for increments in CPython; if multi-process
deployment is used, metrics will be per-process (acceptable for debug scope).
"""
from __future__ import annotations

from typing import Dict, Any, Deque, Tuple, List
import time
from collections import deque

_COUNTERS: Dict[str, int] = {}
_GAUGES: Dict[str, float] = {}
# Histograms: name -> {"buckets": {label: count}, "count": int, "sum": float}
_HIST: Dict[str, Dict[str, Any]] = {}
_START_TS = time.time()

# Rolling event log: (timestamp, name, count)
_EVENTS: Deque[Tuple[float, str, int]] = deque()
_WINDOWS = [60, 300]  # 1m, 5m windows

def _prune(now: float) -> None:
    # Remove events older than max window
    cutoff = now - max(_WINDOWS)
    while _EVENTS and _EVENTS[0][0] < cutoff:
        _EVENTS.popleft()


def incr(name: str, amount: int = 1) -> None:
    _COUNTERS[name] = _COUNTERS.get(name, 0) + amount
    # Record discrete event for rolling rate (only for amount>0)
    if amount > 0:
        now = time.time()
        _EVENTS.append((now, name, amount))
        _prune(now)


def set_gauge(name: str, value: float) -> None:
    _GAUGES[name] = value


def snapshot() -> Dict[str, Any]:
    uptime = time.time() - _START_TS
    now = time.time()
    _prune(now)
    # Compute rolling rates (events per second) per metric for each window
    rolling: Dict[str, Dict[str, float]] = {str(w): {} for w in _WINDOWS}
    if _EVENTS:
        for w in _WINDOWS:
            start_ts = now - w
            # aggregate counts in window
            agg: Dict[str, int] = {}
            for ts, name, count in _EVENTS:
                if ts >= start_ts:
                    agg[name] = agg.get(name, 0) + count
            # convert to per-second rate
            for k, v in agg.items():
                rolling[str(w)][k] = round(v / w, 4)
    return {
        "uptime_sec": round(uptime, 2),
        "counters": dict(sorted(_COUNTERS.items())),
        "gauges": dict(sorted(_GAUGES.items())),
        "rolling_rate_per_sec": rolling,
        "histograms": _HIST,
    }

# -----------------------------
# Histogram Recording
# -----------------------------
_LAT_BUCKETS_MS: List[int] = [50, 100, 200, 400, 800, 1600, 3200]

def record_hist(name: str, value_ms: float) -> None:
    """Record a latency (ms) into fixed buckets."""
    h = _HIST.setdefault(name, {"buckets": {}, "count": 0, "sum": 0.0})
    # determine bucket
    bucket_label = None
    for b in _LAT_BUCKETS_MS:
        if value_ms <= b:
            bucket_label = f"<={b}ms"
            break
    if bucket_label is None:
        bucket_label = ">{}ms".format(_LAT_BUCKETS_MS[-1])
    h["buckets"][bucket_label] = h["buckets"].get(bucket_label, 0) + 1
    h["count"] += 1
    h["sum"] += float(value_ms)


__all__ = ["incr", "set_gauge", "snapshot", "record_hist"]