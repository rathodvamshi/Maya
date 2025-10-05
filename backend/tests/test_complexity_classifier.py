from app.services.telemetry import classify_complexity


def test_complexity_how_to():
    q = "How do I install Node.js on Windows? Step 1: download. Step 2: run installer."
    ans = "First, download the installer... Second, run it... In summary, you're done."
    assert classify_complexity(q, ans) == "how_to"


def test_complexity_recommendation():
    q = "Can you recommend a good sci-fi book?"
    ans = "Dune is a classic..."
    assert classify_complexity(q, ans) == "recommendation"


def test_complexity_explanatory():
    q = "Explain the difference between TCP and UDP"
    ans = "TCP is connection-oriented while UDP is connectionless. In summary, they trade reliability for speed."
    assert classify_complexity(q, ans) == "explanatory"


def test_complexity_factual():
    q = "What is the capital of France?"
    ans = "Paris is the capital of France."
    assert classify_complexity(q, ans) in {"factual", "explanatory"}


def test_complexity_chitchat():
    q = "hi"
    ans = "Hello!"
    assert classify_complexity(q, ans) == "chitchat"


def test_complexity_general():
    q = "I was thinking about productivity habits today"
    ans = "Interesting reflection on habits..."
    assert classify_complexity(q, ans) == "general"


def test_complexity_upgrade_rule():
    q = "What is machine learning?"
    long_answer = (
        "Machine learning is a subset of AI.\n"
        "First, data is collected. Second, models learn patterns.\n"
        "In summary, ML enables predictive capabilities across domains." * 3
    )
    assert classify_complexity(q, long_answer) == "explanatory"