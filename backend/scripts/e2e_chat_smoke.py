"""End-to-end chat smoke test to run inside backend container.

Usage (from host):
    docker compose exec backend python scripts/e2e_chat_smoke.py
"""
import requests
import sys

BASE = "http://localhost:8000"

email = "e2e_tester@example.com"
password = "Passw0rd!"

def main():
    # Register (ignore 400 if already exists)
    # Use new signup route returning access_token + user_id
    r = requests.post(f"{BASE}/api/auth/signup", json={"email": email, "password": password})
    print("register:", r.status_code, r.text[:120])

    # Login
    r = requests.post(f"{BASE}/api/auth/login", data={"username": email, "password": password})
    print("login:", r.status_code)
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)
    token = r.json().get("access_token")
    if not token:
        print("No access token in response")
        sys.exit(1)
    headers = {"Authorization": f"Bearer {token}"}

    # Onboarding
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(
        f"{BASE}/api/user/onboarding",
        json={"name": "Alice", "region": "USA", "preferences": {"cuisine": "Italian"}},
        headers=headers,
    )
    print("onboarding:", r.status_code, r.text[:120])

    # Start new chat
    payload = {"message": "Hi, my name is Alice and I live in Seattle. I love hiking."}
    r = requests.post(f"{BASE}/api/chat/new", json=payload, headers=headers)
    print("chat/new:", r.status_code)
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)
    data = r.json()
    session_id = data.get("session_id")
    print("session_id:", session_id)
    print("assistant:", (data.get("response_text") or "")[:160])
    if not session_id:
        print("No session id returned")
        sys.exit(1)

    # Continue chat
    payload = {"message": "Plan a trip to Paris next month."}
    r = requests.post(f"{BASE}/api/chat/{session_id}", json=payload, headers=headers)
    print("chat/continue:", r.status_code)
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)
    data = r.json()
    print("assistant:", (data.get("response_text") or "")[:200])

    # Feedback correction
    r = requests.post(
        f"{BASE}/api/chat/{session_id}/feedback",
        json={"fact_id": "fake123", "correction": "He lives in Mumbai"},
        headers=headers,
    )
    print("feedback:", r.status_code, r.text)

    # Export memories
    r = requests.post(f"{BASE}/api/memories/export", headers=headers)
    print("export:", r.status_code, r.headers.get("Content-Type"))

    print("E2E chat smoke test completed ✔")

if __name__ == "__main__":
    main()
