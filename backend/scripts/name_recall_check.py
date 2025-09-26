"""Check if assistant greets by name after user introduces themselves.

Steps:
 1) Register/login
 2) Say your name (to trigger extraction)
 3) Ask a follow-up greeting and see if name appears
"""
import requests
import time

BASE = "http://localhost:8000"
email = "name_check@example.com"
password = "Passw0rd!"

r = requests.post(f"{BASE}/auth/register", json={"email": email, "password": password})
print("register:", r.status_code)
r = requests.post(f"{BASE}/auth/login", data={"username": email, "password": password})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Step 1: introduce name
r = requests.post(f"{BASE}/api/chat/new", json={"message": "Hi, my name is Bob."}, headers=headers)
sid = r.json()["session_id"]
print("new:", r.status_code, "sid:", sid)

# Give Celery a moment to process extraction
time.sleep(3)

# Step 2: ask for a greeting
r = requests.post(f"{BASE}/api/chat/{sid}", json={"message": "Can you greet me by name?"}, headers=headers)
print("continue:", r.status_code)
print(r.json()["response_text"][:300])
