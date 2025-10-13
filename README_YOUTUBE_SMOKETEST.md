# YouTube Inline Playback Smoke Test

This quick guide helps you verify the confidence-gated, inline YouTube playback end-to-end.

## 1) Prereqs
- Windows, macOS, or Linux
- Docker (recommended) or local Python 3.11 + Node 18
- A valid YouTube Data API v3 key (for search and ranking)

## 2) Configure environment
1. Copy example env files and fill values:
   - backend/.env — set YOUTUBE_API_KEY and other required keys
   - frontend/.env — ensure REACT_APP_API_URL points to your backend (default http://localhost:8000)

2. Minimal required for this smoke test:
   - backend/.env: set `YOUTUBE_API_KEY=YOUR_KEY`
   - Other AI keys can remain placeholders if you only test the YouTube fast-path and clarification flow.

## 3) Run with Docker (simplest)
- Use the provided scripts (Windows):
  - double-click `docker-up.cmd` or run it in Command Prompt.
- This will start backend (http://localhost:8000), frontend (http://localhost:3000), Redis, and Neo4j.

To stop, run `docker-down.cmd`. Logs: `docker-logs.cmd`.

## 4) Test in the app (modern Chat)
1. Open http://localhost:3000 and sign in (make sure your auth is set up).
2. Go to Chat tab (Modern UI). Try:
   - "Play Chaleya (Hindi) song"
     - Expected: Assistant replies first with text like "▶️ Playing …" then a YouTube player appears as a separate assistant message.
   - "Play chaleya"
     - Expected: Assistant asks a clarifying question. Reply with "Hindi". The next response should play the correct song and embed the player.
3. Use inline controls (Replay/Next/Lyrics). "Next" should pick a related video; "Lyrics" returns a sample block.
4. Scroll away — a PiP mini-player appears; click it to restore.

## 5) Legacy Chat (optional)
- The legacy Chat window also supports client-side YouTube auto-embed and manual Play. If you use it, you may see immediate embeds when your prompt contains a YouTube cue.
- The modern Dashboard path is server-driven: video appears only when the backend is confident.

## 6) Troubleshooting
- If you see "YouTube API key not configured": ensure backend/.env has YOUTUBE_API_KEY and the backend was restarted.
- CORS or 401 errors: make sure you're signed in and REACT_APP_API_URL matches the backend origin.
- Backend restarts with code 1 on Windows: avoid binding conflicts (port 8000 in use) and prefer `docker-up.cmd`.

## 7) What this validates
- Intent extraction with confidence gating
- Clarify-then-play flow for ambiguous requests
- Inline embedding in chat with PiP and controls
- Smart re-ranking of candidates (official channel bias, views, recency)
