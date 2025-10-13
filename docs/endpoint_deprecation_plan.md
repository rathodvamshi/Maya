# Endpoint Deprecation Plan

This document proposes an action plan for endpoints flagged as unused by the audit. Items are grouped by risk; changes should be shipped behind a deprecation header for one release before removal where applicable.

Legend:
- Keep: Needed for internal tooling/ops or expected future use
- Hide: Keep implemented but remove from docs/FE; consider auth-hardening
- Deprecate: Mark with `X-Deprecation` header and log usage; remove later
- Remove: Safe to delete now (no FE/tests references and no ops impact)

## 1) Safe candidates to Remove now
- /api/debug/echo (GET): debugging only; no FE/tests references
- /api/chat/{session_id}/history (GET): duplicate of sessions history
- Legacy auth mirrors (/auth/login, /auth/register, /auth/update-password): prefer /api/auth/*
- /api/memories (GET without trailing slash): duplicate of /api/memories/

## 2) Deprecate next release, then remove
- /api/chat/new/stream (POST): streaming path duplicates `/api/chat/{id}/stream`. Keep one.
- /api/chat/{id}/stream (POST) vs `/api/sessions/{id}/chat` (POST): consolidate on one chat continuation path. Add `X-Deprecation` on the one we choose to retire.
- /metrics/* (GET) (non-API namespace): prefer `/api/metrics/*`. Keep non-API for a release with deprecation header.
- /api/ops/* (celery_health_check, peek_task, list_recent_tasks): if only used ad-hoc, mark deprecated; keep `list_scheduled_tasks`, `revoke`, `celery_inspect`.

## 3) Keep or Hide (internal/admin)
- /api/debug/preferences/{user_id} (GET), /api/debug/metrics (GET): keep for internal debugging; add `admin` tag and enforcement if needed.
- /api/memories/* analytics and distillation endpoints: keep if used by maintenance scripts; otherwise hide for now and add auth-hardening.
- /api/mini-agent/*: likely future-facing; hide in public docs until FE integration lands.

## 4) Memory endpoints needing review
- DELETE /api/memories/{user_id}: dangerous; ensure admin-only; likely Deprecate and replace with soft-delete or export-only.
- POST /api/memories/reembed, /export, /distillation/run: operations endpoints; keep but guard via role checks; not public.

## 5) Owners and next actions
- Auth + Chat consolidation owner: Backend lead
- Ops endpoints owner: Infra/DevOps
- Memories/Analytics owner: Knowledge Graph team
- Debug endpoints owner: Core Platform

## 6) Implementation steps
1. Add `X-Deprecation` response header to targeted endpoints with a sunset date.
2. Add lightweight request logging for deprecated routes (with sampling) to track residual usage.
3. Update backend/ENDPOINTS.md and FE services accordingly.
4. After 1-2 releases with no usage, remove code and tests; keep changelog entry.

## 7) Tracking list (from latest audit)
- Unused items snapshot is in reports/debug_report.json under `unused_endpoints`. Review alongside this plan to mark each item as Keep/Hide/Deprecate/Remove.
