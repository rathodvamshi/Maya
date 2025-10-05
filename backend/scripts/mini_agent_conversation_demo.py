"""Quick mini-agent conversation demo script.

Usage (from backend directory with venv activated):
  python -m scripts.mini_agent_conversation_demo --message-id DEMO_MSG \
      --questions "What does this code do?" "Summarize key points" --selection "Some highlighted text here"

This will:
  1. Ensure a mini thread for the given message id.
  2. Optionally create/add a snippet from --selection.
  3. Send each question and print the assistant reply.
  4. Request a summary at the end.

Assumptions:
  - Server running locally at http://127.0.0.1:8000
  - Auth is disabled for local dev OR you have session/cookie already accepted; if auth required, adapt headers.
"""
from __future__ import annotations
import argparse, sys, time
import json
import textwrap
from typing import List, Optional

import requests

BASE = "http://127.0.0.1:8000/api/mini-agent"


def ensure_thread(message_id: str):
    r = requests.post(f"{BASE}/threads/ensure", json={"message_id": message_id})
    r.raise_for_status()
    return r.json()


def add_snippet(thread_id: str, text: str):
    r = requests.post(f"{BASE}/threads/{thread_id}/snippets/add", json={"text": text})
    r.raise_for_status()
    return r.json()


def send_message(thread_id: str, snippet_id: str, content: str):
    r = requests.post(f"{BASE}/threads/{thread_id}/messages", json={"snippet_id": snippet_id, "content": content})
    r.raise_for_status()
    return r.json()


def summarize(thread_id: str):
    r = requests.post(f"{BASE}/threads/{thread_id}/summarize")
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--message-id", required=True, help="Arbitrary message id anchor for the mini agent thread")
    ap.add_argument("--selection", help="Optional highlighted snippet text")
    ap.add_argument("--questions", nargs="*", default=["Explain this", "Summarize"], help="Questions to ask")
    args = ap.parse_args()

    print("[1] Ensuring thread ...")
    thread_info = ensure_thread(args.message_id)
    thread_id = thread_info["mini_thread_id"]
    print("    Thread:", thread_id, "Session:", thread_info.get("session_id"))

    snippet_id: Optional[str] = None
    if args.selection:
        print("[2] Adding snippet from selection ...")
        snip = add_snippet(thread_id, args.selection.strip())
        snippet_id = snip["snippet_id"]
        print("    Snippet:", snippet_id)
    else:
        # Create a generic snippet if none exists yet
        if not thread_info.get("snippets"):
            print("[2] Creating default snippet from first question ...")
            basis = args.questions[0][:160]
            snip = add_snippet(thread_id, basis)
            snippet_id = snip["snippet_id"]
        elif thread_info.get("snippets"):
            snippet_id = thread_info["snippets"][0]["snippet_id"]

    # Fallback if still none
    if not snippet_id:
        print("ERROR: Could not determine a snippet id; aborting.")
        sys.exit(1)

    for idx, q in enumerate(args.questions, start=1):
        print(f"[Q{idx}] {q}")
        resp = send_message(thread_id, snippet_id, q)
        # Assistant text is in 'assistant_text'
        print(textwrap.indent(resp.get("assistant_text", "<no assistant_text>"), prefix="    A> "))
        # Small pause for readability
        time.sleep(0.4)

    print("\n[Summary] Requesting summary...")
    summary_resp = summarize(thread_id)
    print(textwrap.indent(summary_resp.get("summary", "<no summary>"), prefix="    S> "))

    print("\nDone.")

if __name__ == "__main__":
    main()
