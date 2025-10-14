"""Quick smoke test for reminder_sweep.

Usage (from backend/ directory with venv activated):
    python scripts/reminder_smoke.py --email you@example.com --title "Test Reminder" --offset -30

Creates a task due 30s ago so the next sweep (runs every 60s) should email immediately.

You can then watch Celery worker logs for lines like:
    [Reminders] Email queued task_id=... user_id=... to=...
    [Reminders] Sweep complete scanned=1 dispatched=1 emailed=1 skipped_recent=0 window=60s

Requires: valid Mongo connection & email SMTP settings in .env.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import db_client


def create_due_task(title: str, email: str, user_id: str | None, offset_seconds: int) -> str:
    tasks = db_client.get_tasks_collection()
    now = datetime.utcnow()
    due_time = now + timedelta(seconds=offset_seconds)
    task_id = ObjectId()
    doc = {
        "_id": task_id,
        "user_id": user_id or "smoke-user",
        "title": title,
        "description": "Smoke test task for reminder sweep.",
        "due_date": due_time,
        "notify_channel": "email",
        "email": email,
        "status": "todo",
        "created_at": now,
        "updated_at": now,
    }
    tasks.insert_one(doc)
    return str(task_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Smoke Reminder", help="Task title")
    parser.add_argument("--email", required=True, help="Destination email")
    parser.add_argument("--user", default="smoke-user", help="User id to associate")
    parser.add_argument("--offset", type=int, default=-30, help="Seconds offset from now (negative = past due)")
    args = parser.parse_args()

    if not db_client.healthy():
        print("[ERROR] Database not healthy; aborting.")
        return
    task_id = create_due_task(args.title, args.email, args.user, args.offset)
    print(f"[OK] Created task {task_id} due at offset {args.offset}s. Wait for next sweep (≤60s).")


if __name__ == "__main__":
    main()
