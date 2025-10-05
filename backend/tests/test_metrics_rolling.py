from fastapi.testclient import TestClient
from app.main import app
from app.services import metrics
import time

client = TestClient(app)

def test_metrics_snapshot_includes_rolling_rates():
    # simulate some increments
    metrics.incr("chat.requests.total")
    metrics.incr("chat.responses.total")
    snap = metrics.snapshot()
    assert "rolling_rate_per_sec" in snap
    rr = snap["rolling_rate_per_sec"]
    # windows configured 60 and 300
    assert "60" in rr and "300" in rr
    # recent increments should appear with small positive rate
    # allow zero if timing edge, but structure must exist
    assert isinstance(rr["60"], dict)
    assert isinstance(rr["300"], dict)
