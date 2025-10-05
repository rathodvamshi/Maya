"""Automated smoke script for suggestions / tone / streaming validation.

Usage:
  python scripts/suggestions_smoke.py --token <JWT> [--api http://localhost:8000]

What it does:
  1. Streaming first factual question (answer first, suggestions after)
  2. Non-stream deep explanation -> expect summary/examples suggestions
  3. Tone switch (playful -> formal) and re-ask a factual question
  4. Opt-out test ("no suggestions")
  5. Repeated question 3x to check dedupe
  6. Emotion/context test (anxious message)

Outputs are printed with simple separators; suggestions lines starting with '➝' are highlighted.
"""
from __future__ import annotations

import httpx
import asyncio
import argparse
import sys
from typing import Optional

DEFAULT_API = "http://localhost:8000"


def _headers(token: str):
    return {"Authorization": f"Bearer {token}"}


async def stream_first_message(client: httpx.AsyncClient, api_base: str, token: str, message: str) -> Optional[str]:
    url = f"{api_base}/api/chat/new/stream"
    print(f"\n[STREAM START] {message}")
    async with client.stream("POST", url, json={"message": message}, headers=_headers(token)) as resp:
        print("Status:", resp.status_code)
        sid = resp.headers.get("X-Session-Id")
        print("Session-ID:", sid)
        print("-- Stream Output --")
        async for chunk in resp.aiter_text():
            if chunk:
                sys.stdout.write(chunk)
                sys.stdout.flush()
        print("\n-- End Stream --")
        return sid


async def post_message(client: httpx.AsyncClient, api_base: str, token: str, session_id: str, message: str):
    url = f"{api_base}/api/chat/{session_id}"
    r = await client.post(url, json={"message": message}, headers=_headers(token))
    print(f"\n[CONTINUE] {message}\nStatus: {r.status_code}")
    if r.status_code == 200:
        txt = r.json().get("response_text")
        print(txt)
    else:
        print(r.text)


async def set_tone(client: httpx.AsyncClient, api_base: str, token: str, tone: str):
    url = f"{api_base}/api/user/preferences"
    r = await client.post(url, json={"tone": tone}, headers=_headers(token))
    print(f"[SET TONE] {tone} -> {r.status_code}")


async def run_flow(api_base: str, token: str):
    async with httpx.AsyncClient(timeout=None) as client:
        # 1. Streaming factual short
        session_id = await stream_first_message(client, api_base, token, "What is the capital of Japan?")
        if not session_id:
            print("Failed to obtain session id from streaming endpoint; aborting.")
            return

        # 2. Deep explanation (non-stream)
        await post_message(client, api_base, token, session_id, "Explain quantum computing in detail with analogies and multiple paragraphs.")

        # 3. Tone switch to playful, ask recommendation
        await set_tone(client, api_base, token, "playful")
        await post_message(client, api_base, token, session_id, "Recommend a relaxing music playlist")

        # 4. Tone switch to formal, ask how-to
        await set_tone(client, api_base, token, "formal")
        await post_message(client, api_base, token, session_id, "How do I create a Python virtual environment?")

        # 5. Opt-out test
        await post_message(client, api_base, token, session_id, "Explain photosynthesis (no suggestions)")

        # 6. Repeated factual to test dedupe
        for i in range(1, 4):
            await post_message(client, api_base, token, session_id, f"What is the capital of Japan? ({i})")

        # 7. Emotion / anxiety test
        await set_tone(client, api_base, token, "supportive")
        await post_message(client, api_base, token, session_id, "I'm anxious about tomorrow 😬")

        print("\n[FLOW COMPLETE]")


def main():
    parser = argparse.ArgumentParser(description="Suggestion & streaming smoke test")
    parser.add_argument("--token", required=True, help="JWT access token")
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    args = parser.parse_args()
    asyncio.run(run_flow(args.api.rstrip("/"), args.token))


if __name__ == "__main__":
    main()
