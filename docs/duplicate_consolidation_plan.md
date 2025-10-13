# Duplicate Consolidation Plan

Based on the audit report (`reports/debug_report.json`), prioritize the following low-risk extractions into common utilities. Avoid behavior changes; only refactor repeats to call shared helpers.

## Backend targets

1) Chat router repeated response helpers (hashes around L1318-L1702 in chat.py)
- Extract to `app/utils/chat_response.py`:
  - build_stream_headers()
  - normalize_history()
  - emit_metrics_for_segment()

2) Auth router duplicate field validations (auth.py L78-L315)
- Extract to `app/utils/validation.py`:
  - normalize_email()
  - validate_password_strength()

3) Persona/YouTube shared formatting (chat.py L590-597 ~ youtube.py L78-85)
- Extract to `app/utils/text.py`:
  - truncate_with_ellipsis(text, limit)
  - safe_markdown(text)

4) Dashboard/Profile repetitive list pagination (dashboard.py ~ profile.py)
- Extract to `app/utils/paging.py`:
  - parse_pagination_params(request)
  - paginate(cursor, limit, to_dto)

5) Sessions vs Chat overlap (session title/generation)
- Extract to `app/services/session_utils.py`
  - generate_session_title(history)
  - rename_session(session_id, title)

## Frontend targets

1) API client utilities (axios wrappers already exist)
- Create `src/utils/http.js`:
  - withBearer(token)
  - toQuery(params)

2) Repeated date formatting & truncation across components
- Create `src/utils/format.js`:
  - fmtDate(date)
  - truncate(text, n)

## Process
- Create utils with tests (happy path + 1 edge case).
- Replace duplicate blocks incrementally (PRs per area).
- Run full backend tests and FE smoke scripts each PR.

## Non-goals (for now)
- Changing public API shapes.
- Deep redesigns in chat/session architecture.

## Tracking
- Check off items as commits reference this plan.
