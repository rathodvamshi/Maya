# Project MAYA Backend Architecture & Optimization Deep Dive

_Last updated: 2025-09-26_

This document provides a comprehensive breakdown of the backend system: endpoints, data flow, memory layers, background processing, performance, security posture, and concrete recommendations for lowering cost while improving speed and accuracy.

---
## 1. High-Level Architecture

Component | Purpose | Tech
--------- | ------- | ----
FastAPI App | HTTP API layer (auth, chat, sessions, feedback, memory export) | FastAPI
MongoDB | Primary persistence (users, sessions, tasks, feedback) | PyMongo
Redis (async + sync clients) | Rate limiting, per-session state, short-term conversation memory, caching | redis-py asyncio & sync
Neo4j | Long-term structured fact graph (entities, relationships, user facts) | neo4j Python async + sync drivers
Pinecone | Semantic memory: vector similarity over message embeddings | pinecone >=3
AI Providers | LLM responses & embedding generation | Gemini, Cohere, Anthropic
Celery + Redis | Background jobs (fact extraction, embeddings, prefetch) | Celery

### Memory Layering Strategy
Layer | Source | Role
----- | ------ | ----
Short-Term | Redis list (conversation history) | Fast recall of last ~50 exchanges
Session Transcript | MongoDB session `messages` | Durable canonical history
Semantic Memory | Pinecone per-message embeddings | Retrieve similar past content
Structured Facts | Neo4j graph relationships | Personalization & factual grounding
Prefetched Context | Redis ephemeral cache | Domain-specific enrichment (e.g., travel destinations)

---
## 2. Data Models (Mongo Collections)
Collection | Key Fields | Notes / Indexes
---------- | ---------- | --------------
users | email (unique), hashed_password, profile, last_seen | Index on email, last_seen
sessions | userId, messages[{sender,text}], title, createdAt | Index userId+lastUpdatedAt (should be lastUpdatedAt, code uses lastUpdatedAt vs index creation lastUpdatedAt vs lastUpdatedAt? Confirm spelling)
chat_logs (legacy) | email, sender, text, timestamp | Legacy endpoints only
tasks | email, content, due_date_str, status | Index email+status
feedback | userId, sessionId, ratedMessage, chatHistory | For future analytics
user_profiles | facts[{key,value}] (ad‑hoc) | Only used by sessions router fact saving

Neo4j: `(:User {id, name})` + dynamic nodes + typed relationships with optional `fact_id`.

Pinecone Vectors:
- Index: `maya` (dimension 1024)
- Message vector id: `{user_id}:{session_id}:{timestamp}:{role}`
- Metadata: user_id, session_id, role, timestamp, text, kind=message

---
## 3. Endpoint Inventory

### Auth (`/api/auth` & legacy `/auth`)
Method | Path | Description | Auth?
------ | ---- | ----------- | -----
POST | /signup | Register + return access token (no refresh) | Public
POST | /register | Register (returns user public data) | Public
POST | /login | JWT access + refresh tokens | Public

### User (`/api/user`)
GET | /onboarding-questions | Static questions | Auth
POST | /onboarding | Saves profile (Mongo), updates Neo4j, caches profile in Redis | Auth

### Chat (`/api/chat`)
POST | /new | Create new session with first message | Auth
POST | /new/stream | Same, streaming response (chunked) | Auth
POST | /{session_id} | Continue session (context aggregation) | Auth
POST | /{session_id}/stream | Streaming continuation | Auth
GET | /history | Legacy flat history (chat_logs) | Auth
DELETE | /history/clear | Clear legacy history + Redis state | Auth
GET | /{session_id}/history | Last N messages for a session | Auth
POST | /{session_id}/feedback | Queue fact correction | Auth
Task Ops | /tasks*, CRUD for tasks | Auth

### Sessions (`/api/sessions`)
POST | / | Create session from given initial messages | Auth
GET | / | List sessions (no messages) | Auth
GET | /{session_id} | Paginated message slice (reverse slice via projection) | Auth
DELETE | /{session_id} | Delete a session | Auth
POST | /{session_id}/chat | Alternate chat flow (includes NLU-driven task/fact logic) | Auth

### Feedback (`/api/feedback`)
POST | / | Store rated message + chat snapshot | Auth
POST | /correction | Queue fact correction (Celery) | Auth

### Memories (`/api/memories`)
POST | /export | Export sessions + facts + Pinecone meta note | Auth
DELETE | /{user_id} | Delete all user memory layers | Auth (self only)

### Health (`/health`)
GET | / | Check Neo4j, Redis, Pinecone status (self-heal attempts) | Public

### Root (`/`)
GET | / | Simple status JSON | Public

---
## 4. Chat Workflow (Detailed)

Phase | New Session (`/api/chat/new`) | Continue (`/api/chat/{id}`) | Sessions Router Flow (`/api/sessions/{id}/chat`)
----- | ----------------------------- | --------------------------- | -----------------------------------------------
State Load | (none yet) sets Redis state `general_conversation` | Redis: session:state + last 10 Mongo messages | Uses `gather_memory_context` (state + redis history + embedding recall)
Context Retrieval | Pinecone similar messages (threadpool) + Neo4j facts (async) | Same | Same + merges Redis conversation history fallback
NLU / Intent | Simple regex only for planning trips | Same + triggers prefetch task | Rich NLU via AI prompt classification (create_task, fetch_tasks, save_fact, general_chat)
Prefetch | If PLAN_TRIP -> Celery prefetch_destination_info | Same | Not implemented (in that path)
Response Generation | `ai_service.get_response()` with system prompt + context | Same (with history & state) | Same but state derived from NLU mapping
Persistence | Insert session with first 2 messages | Update session: push 2 messages | Push both messages to session
Embeddings | Celery `store_embedding_task` for both messages | Celery for both messages | Inline coordinator upsert + Celery fallback
Fact Extraction | Celery `extract_and_store_facts` | Same | Coordinator schedules extraction via Celery
State Update | Set to `general_conversation` | Possibly transitions to `planning_trip` | Updated via coordinator call based on action

---
## 5. AI Service & Prompting

`MAIN_SYSTEM_PROMPT` (not shown here) is filled with:
- neo4j_facts
- pinecone_context
- state
- assembled recent history
- current user prompt

Providers attempted in order: Cohere → Gemini → Anthropic (NOTE: defined `AI_PROVIDERS = ["cohere", "gemini", "anthropic"]` but gemini_keys rotation internally for Gemini). Failures recorded with timestamp; providers enter cooldown `AI_PROVIDER_FAILURE_TIMEOUT` (300s default).

Issues / Observations:
1. Provider order may not optimize cost (Cohere is attempted before Gemini though Gemini Flash is cheaper in some tiers). Need a cost/latency policy layer.
2. No token budgeting: all context concatenated blindly → potential waste.
3. No streaming from providers (stream simulated by splitting final result).
4. History labeling uses "Human" / "Assistant" (OK) but mismatch with other formats (role-based) could reduce grounding quality.
5. Fact extraction prompt expects pure JSON but fallback tries multiple providers; no strict schema validation.

---
## 6. Memory Coordinator vs Chat Router Duplication

There are two paradigms:
- Chat Router (`chat.py`) implements its own context gathering (`_gather_context`).
- Sessions Router (`sessions.py`) uses `memory_coordinator.gather_memory_context` (richer: history + layered state + embeddings + facts) and `post_message_update`.

Recommendation: Unify on `memory_coordinator` to reduce drift and bugs.

---
## 7. Background Processing (Celery)
Task | Purpose | Risks / Notes
---- | ------- | ------------
store_embedding_task | Generate + upsert embedding per message | Re-initializes Pinecone each run (inefficient)
extract_and_store_facts_task | Parse exchange, add entities/relationships | Potential JSON hallucinations; no size guard
prefetch_destination_info_task | Future travel enrichment | Stubbed (commented body)
process_feedback_task | Apply fact correction | Minimal validation (fact ownership)
summarize_and_archive_task | Placeholder for session summarization | Not implemented

---
## 8. Performance & Cost Bottlenecks
Area | Issue | Impact
---- | ----- | ------
Prompt Construction | Full history concatenated (up to 50) without token limit | Higher tokens → cost & latency
Dual Redis Implementations | `redis_service` (async) + `redis_cache` (sync) maintain similar state concepts | Cognitive + maintenance overhead
Embedding Upserts | Each message triggers separate Celery task (two tasks per user exchange) | Task overhead, cold starts
Pinecone Init | `store_embedding_task` calls `initialize_pinecone()` per task | Extra latency + API calls
Neo4j Fact Extraction | Runs for every pair of messages synchronously in Celery | Costly provider usage; maybe batch
NLU via LLM | In sessions router `nlu.get_structured_intent` uses a full LLM call | Expensive for frequent short commands
Provider Ordering | Cohere first irrespective of latency/cost/performance | Sub-optimal economics
Streaming | Simulated after full generation | Slow TTFB perception for long answers
Indexes | Missing indexes on some query patterns (e.g., `sessions.createdAt` already used but ok; might need `lastUpdatedAt`) | Query latency at scale
Tasks Query | tasks.find without projection; returns full docs except minimal fields extracted later | Slight overhead

---
## 9. Security Review
Category | Finding | Recommendation
-------- | ------- | -------------
JWT | Single SECRET_KEY used for both access & refresh tokens | Optionally rotate & separate secrets
Token Revocation | No blacklist/invalidation on refresh | Add refresh token store w/ jti + revocation TTL
Password Hash | bcrypt via passlib (good) | Add password length validation
AuthZ | Only ownership checks on session/task; no role concept | Add roles (user/admin) if admin endpoints planned
Input Validation | Many raw strings accepted (task dates, feedback) | Add stricter pydantic validation + length limits
Rate Limiting | Per-user sliding window via Redis key bucket | Add global fallback or per-endpoint tuning
Prompt Injection | Facts + context concatenated without sanitization | Escape or delimit external contexts consistently
NLU Fact Saving | `save_fact` path writes user_profiles w/ unbounded key sizes | Sanitize key length & character set
Feedback Correction | No check that fact belongs to user | Query relationship user ownership before applying
Neo4j Queries | Mostly parameterized (good) | Keep avoiding string interpolation for labels if dynamic
Export | Exports all sessions fully | Consider redacting sensitive messages or adding filter
CORS | Only localhost:3000 (safe dev) | Harden for production with env-based allowlist

---
## 10. Concrete Optimization Recommendations

### 10.1 Quick Wins (Low Effort / High Impact)
1. Unify Memory Gathering: Replace `_gather_context` in `chat.py` with `memory_coordinator.gather_memory_context`.
2. Add Token Budgeting: Before calling LLM, trim history to a token ceiling (approx via message char length heuristic).
3. Batch Embedding Tasks: Combine user & assistant message into single `store_embeddings_batch` task.
4. Avoid Reinitializing Pinecone: Move `initialize_pinecone()` call out of each Celery embedding task.
5. Add Index: Ensure index on `sessions.lastUpdatedAt` (code currently sets lastUpdatedAt but index creation uses lastUpdatedAt? Validate naming).
6. Cache Neo4j Facts: Cache last facts string per user in Redis for short TTL (e.g., 60s) to reduce Neo4j queries every turn.
7. Cheap Deterministic NLU: Replace LLM-based `nlu.get_structured_intent` for simple patterns with spaCy/regex + optional fallback only when ambiguous.
8. Limit Fact Extraction Frequency: Extract every N messages or when message length > threshold; add a rate gate in Celery.
9. Streaming Real-Time: Use Gemini / Anthropic streaming APIs to improve perceived latency.
10. Introduce Provider Policy: Attempt cheapest—Gemini Flash → Cohere → Anthropic (configurable).

### 10.2 Mid-Term Improvements
1. Conversation Summarization: Periodically summarize old messages and replace with a summary token to lower prompt size.
2. Embedding Pre-Queue: Use an in-process asyncio queue and batch flush to Celery or directly to Pinecone when size threshold reached.
3. Structured Fact Schema: Introduce validation schema for `extract_facts_from_text` to reduce malformed graph writes.
4. Observability: Add OpenTelemetry spans (FastAPI middleware + instrument Celery tasks) + per-provider latency metrics.
5. Soft Deletes & Archiving: Mark old sessions `isArchived` and move embeddings to summary-only representation.
6. Refresh Token Rotation: Issue new refresh token per use; store hashed jti in Redis with TTL.
7. Cost Dashboard: Persist provider usage counts/tokens in Mongo for anomaly detection.
8. Multi-Turn State Machine: Formalize states (ENUM: general, planning_trip, task_management, memory_update) to drive system prompt variations.

### 10.3 Long-Term Enhancements
1. Vector DB Abstraction: Interface to allow switching Pinecone ↔ open-source (Qdrant) for cost savings.
2. Graph-Augmented Retrieval: Use Neo4j path expansion to enrich semantic context (e.g., top connected preference nodes) before LLM call.
3. Fine-Tuned Lightweight NLU Model: Distill classification (create_task/fetch_tasks/save_fact/chat) for <1ms inference locally.
4. Embedding Deduplication: Hash normalized text and skip re-embedding duplicates.
5. Hybrid RAG Ranking: Use embedding similarity + recency + graph relevance scorers for context selection.
6. Prompt Versioning: Maintain prompt templates with semantic versioning and ab testing toggles.
7. Differential Privacy / PII Scrubbing: Preprocess and mask potential sensitive fragments before vectorizing/exporting.

---
## 11. Suggested Code Refactors (Outline)
Refactor | Rationale
-------- | ---------
`chat.py` context unify | Single source of truth for memory logic
Add `services/context_manager.py` | Encapsulate logic for assembling final prompt (budget aware)
`embedding_service` batch API | Reduce Celery overhead (fewer tasks)
Introduce `tasks/schedules.py` | Centralize periodic & gating logic
Add `schemas/` module | Centralized Pydantic models with stricter constraints (length, enums)
`
---
## 12. Sample Implementation Snippets (Conceptual)

### Token-Aware History Trimming (Pseudo-Python)
```python
def trim_history(messages, max_chars=6000):
    total = 0
    trimmed = []
    for m in reversed(messages):  # oldest last
        size = len(m['text'])
        if total + size > max_chars:
            break
        trimmed.append(m)
        total += size
    return list(reversed(trimmed))
```
Call before `ai_service.get_response()`.

### Batched Embedding Task
```python
@celery_app.task(name="store_embeddings_batch")
def store_embeddings_batch(batch: list[dict]):
    pinecone_service.initialize_pinecone()
    for item in batch:
        pinecone_service.upsert_message_embedding(**item)
```

---
## 13. Prioritized Roadmap
Priority | Item | Effort (est) | Impact (Cost/Speed/Accuracy)
-------- | ---- | ----------- | ---------------------------
P0 | Unify context + trim history + provider reorder | 0.5–1 day | High / High / Medium
P0 | Batch embeddings + remove redundant init | 0.5 day | High / High / Low
P1 | Cache Neo4j facts (TTL) | 0.25 day | Medium / Medium / Low
P1 | Gate fact extraction frequency | 0.25 day | Medium / Medium / Medium
P1 | Regex/spaCy NLU primary path | 0.5 day | Medium / Medium / Low
P2 | Conversation summarization | 1–2 days | High / High / Medium
P2 | Observability instrumentation | 1 day | Medium / Medium / Medium
P2 | Refresh token rotation | 0.75 day | Low / Low / Security High
P3 | Graph-enriched retrieval | 2–3 days | Medium / Medium / High
P3 | Vector backend abstraction | 2 days | Cost Flexibility High

---
## 14. Accuracy Improvement Levers
Technique | Description | Tradeoff
--------- | ----------- | --------
Selective Context | Include top K semantic + top recency + top graph path | Slight complexity increase
Dynamic Prompt Sections | Omit empty sections to reduce noise | Minimal complexity
Preference Weighting | Tag embeddings with topic; re-rank by user preference edges | Requires metadata expansion
Structured Facts Reverification | Periodically prompt LLM to validate conflicting facts | Extra provider calls

---
## 15. Cost Control Strategy
Measure | Action
------- | ------
Provider Cost | Implement provider scorecard: (latency rolling avg, failure rate, $/1K tokens) → dynamic ordering
Token Reduction | Summaries + trimming + stop including "No facts available" literal text; replace with shorter placeholders
Embedding Volume | Deduplicate + batch + only embed user messages (optionally skip assistant)
Fact Extraction | Run every 3rd turn or for messages > N chars
Prefetch Tasks | Only launch if user intent confidence > threshold

---
## 16. Risk Register
Risk | Description | Mitigation
---- | ----------- | ---------
Silent Provider Cooldown | All providers cooling → degraded user response | Add alert if all providers fail consecutively > X
Graph Drift | No versioning of facts; corrections overwrite | Store fact history or changelog node
Redis Loss | If Redis down, state resets and history shrinks | Graceful fallback already; add warning metric
Pinecone Dimension Drift | Embedding model change would break index | Enforce dimension constant & version suffix index name
Unbounded Session Growth | Large messages list increases query cost | Summarization + pagination (already partial) + archive flag usage

---
## 17. Action Checklist Snapshot
- [ ] Refactor: unify `_gather_context` with `memory_coordinator`
- [ ] Add token trimming utility
- [ ] Reorder providers + configurable strategy
- [ ] Batch embedding Celery task
- [ ] Cache Neo4j facts in Redis (TTL 60s)
- [ ] Add NLU fast path (regex/spaCy) before LLM call
- [ ] Gate fact extraction frequency
- [ ] Implement streaming from provider SDKs
- [ ] Add summarization cron (archive older history)
- [ ] Strengthen feedback fact ownership validation

---
## 18. Summary
The current architecture is robustly modular with clear memory stratification. Major gains are available through unifying duplicated logic, enforcing token & task gating, batching background work, and adopting a dynamic provider strategy. These changes can materially reduce cost and latency without sacrificing personalization quality, while laying groundwork for scalable retrieval and advanced graph-based reasoning.

Feel free to request focused implementation steps for any section; this document is a living artifact.
