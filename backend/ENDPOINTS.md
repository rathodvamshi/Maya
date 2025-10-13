# API Endpoint Overview

This document enumerates the current FastAPI endpoints, grouped by router, noting auth requirements and purpose. Use it to align frontend calls and for QA smoke validation.

## Authentication
All `/api/*` routes (except `/api/auth/signup`, `/api/auth/login`, `/api/auth/register`) require a Bearer JWT.
Legacy auth routes are also exposed under `/auth/*` for compatibility.

## Routers

### Auth (`auth.py`)
- POST `/api/auth/signup` → {access_token, user_id}
- POST `/api/auth/register` → Register (legacy style)
- POST `/api/auth/login` (form: username, password) → {access_token, refresh_token, user_id, email}
- Legacy mirrors: `/auth/register`, `/auth/login`

### Chat (`chat.py`)
Prefix: `/api/chat`
- POST `/api/chat/new` → Start session {session_id, response_text}
- POST `/api/chat/new/stream` → Streaming plain text (X-Session-Id header)
- POST `/api/chat/{session_id}` → Continue chat {response_text}
- POST `/api/chat/{session_id}/stream` → Streaming continuation
- Tasks:
  - POST `/api/chat/tasks` → Create task
  - PUT `/api/chat/tasks/{task_id}` → Update task
  - PUT `/api/chat/tasks/{task_id}/done` → Mark done
  - GET `/api/chat/tasks` → Pending tasks
  - GET `/api/chat/tasks/history` → Completed (recent)

### Sessions (`sessions.py`)
Prefix: `/api/sessions`
- POST `/api/sessions/` → Create session from provided messages array
- GET `/api/sessions/` → List sessions (id, title, createdAt)
- GET `/api/sessions/{session_id}` → Paginated messages (query: page, limit)
- DELETE `/api/sessions/{session_id}` → Delete session
- POST `/api/sessions/{session_id}/chat` → Alternate chat continuation (nlu + tasks + memory layers)

NOTE: There is functional overlap between `/api/chat/{session_id}` and `/api/sessions/{session_id}/chat`. Decide which abstraction the frontend should standardize on; currently frontend uses the chat router (`/api/chat/...`).

### Feedback (`feedback.py`)
Prefix: `/api/feedback` (auth)
- POST `/api/feedback/` → Store rating + history
- POST `/api/feedback/correction` → Queue fact correction (Celery)

### Health (`health.py`)
- GET `/health/` → Service status
- GET `/api/health` → Alias

### Debug (`debug.py`)
Prefix: `/api/debug`
- GET `/api/debug/preferences/{user_id}` → Inferred + raw behavioral prefs
- GET `/api/debug/metrics` → Metrics snapshot (subset)

### Metrics (`metrics.py`)
- GET `/metrics/hedge`
- GET `/metrics/all`
(Suggestion: Mirror under `/api/metrics/*` for consistency.)

### User (`user.py`)
Prefix: `/api/user`
- GET `/api/user/onboarding-questions`
- POST `/api/user/onboarding`
- POST `/api/user/preferences`
- GET `/api/user/preferences`

Preferences API details:
- POST `/api/user/preferences`
  - Body fields (all optional):
    - `enable_emojis`: boolean
    - `enable_emotion_persona`: boolean
    - `tone`: string; allowed: `fun`, `playful`, `formal`, `neutral`, `supportive`, `enthusiastic`
  - Behavior:
    - `tone` is normalized: `fun` → `playful`.
    - Stored values use simple strings: `emoji` and `emotion_persona` are `"on"|"off"`, `tone` is the normalized tone.
  - Response: `{ "updated": {<keys changed>}, "effective": {<current preferences>} }`
  - Errors: `400` on invalid tone.
- GET `/api/user/preferences`
  - Returns: `{ "effective": {<current preferences>} }`

### Memory & Services (Indirect)
No direct user-facing endpoints for Pinecone/Neo4j/Redis; exposed via chat/session workflows.

## Inconsistencies / Improvement Targets
1. Duplicate chat continuation endpoints (`/api/chat/{id}` vs `/api/sessions/{id}/chat`). Recommend unifying and deprecating one or making their responsibilities distinct (e.g., sessions route = structural management, chat route = conversational streaming + fast-path heuristics).
2. Health & Metrics outside `/api/` namespace (added `/api/health` alias; metrics still outside).
3. No global `/api/info` or `/api/version` endpoint.
4. Rate limiting not exempting health/metrics fully (health path partially exempt due to prefix check). Could explicitly allow metrics.
5. Missing standardized error envelope. Add exception handlers for 422/401/404 to return `{error: {code, message}}`.

## Smoke Test Matrix (Recommended)
| Endpoint | Method | Auth | Expected |
|----------|--------|------|----------|
| / | GET | No | 200 JSON status |
| /health/ | GET | No | 200 JSON services |
| /api/auth/login | POST form | No | 200 token |
| /api/chat/new | POST JSON {message} | Yes | 200 session + text |
| /api/chat/{id} | POST JSON {message} | Yes | 200 text |
| /api/sessions/ | GET | Yes | 200 array |
| /api/user/preferences | GET | Yes | 200 prefs |
| /metrics/all | GET | No (maybe) | 200 metrics |

Automate via `scripts/api_smoke.py` (extend as needed).

## Next Steps (Optional Enhancements)
- Add `/api/metrics/*` mirror.
- Add `/api/info` (commit hash, build time, enabled providers, CORS origins).
- Implement consistent error handler.
- Add deprecation warning header for whichever chat path is to be removed.
- Add integration tests for memory retrieval timing budgets.
