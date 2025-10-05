from app.services import metrics

def test_histogram_recording():
    metrics.record_hist("provider.latency.test", 123)
    metrics.record_hist("provider.latency.test", 75)
    snap = metrics.snapshot()
    h = snap["histograms"].get("provider.latency.test")
    assert h is not None
    assert h["count"] == 2
    assert h["sum"] >= 198
    # bucket labels present
    assert any(label.startswith("<=") for label in h["buckets"].keys()) or any(label.startswith(">") for label in h["buckets"].keys())
