"""Simple synchronous smoke test for key API endpoints.
Run with: python -m scripts.api_smoke <BASE_URL> <TOKEN>
TOKEN is optional (Bearer token). If not provided, only public endpoints tested.
"""
import sys, requests, json

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None

hdrs = {"Accept": "application/json"}
if TOKEN:
    hdrs["Authorization"] = f"Bearer {TOKEN}"

results = []

def check(name, method, path, **kwargs):
    url = BASE.rstrip("/") + path
    try:
        r = requests.request(method, url, headers=hdrs, timeout=8, **kwargs)
        ok = r.status_code < 500
        results.append({"name": name, "status": r.status_code, "ok": ok, "path": path})
    except Exception as e:
        results.append({"name": name, "status": "ERR", "ok": False, "error": str(e), "path": path})

# Public-ish endpoints
check("root", "GET", "/")
check("health", "GET", "/health/")

if TOKEN:
    # Authenticated endpoints
    check("sessions list", "GET", "/api/sessions/")
    # Chat new requires message body
    check("chat new (expected 422 or 400 if no body)", "POST", "/api/chat/new")

print(json.dumps(results, indent=2))
