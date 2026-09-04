# Proofly Implementation Plan

Contracts are frozen in `docs/ARCHITECTURE.md` and `docs/API.md`. Phases map to the
master build prompt §54. Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## Phase 1 — Repository inspection + skeleton
- [x] Inspect repo (was empty)
- [x] docs/ENGINEERING_RULES.md, docs/ARCHITECTURE.md, docs/API.md, docs/IMPLEMENTATION_PLAN.md
- [x] .env.example, docker-compose.yml

## Phase 2 — Supabase schema + Flyway + backend domain
- [x] Flyway migrations for full schema (12 tables, pgvector HNSW index, constraints)
- [x] JPA entities + repositories

## Phase 3 — Spring Boot research job APIs
- [x] Controllers/DTOs/services for public API (docs/API.md)
- [x] Ownership/security enforcement (404-not-403 choke point)

## Phase 4 — Redis queue/checkpoint infrastructure (backend side)
- [x] Job queue + bounded-concurrency dispatcher + SSE Redis pub/sub relay
- [x] Stale-job reaper enforcing RESEARCH_MAX_DURATION_SECONDS

## Phase 5 — Python FastAPI AI service skeleton
- [x] App structure, health endpoint, internal API client to backend

## Phase 6 — Gemini provider abstraction
- [x] LLMProvider (generate/generateStructured/embed) + Gemini impl + deterministic mock

## Phase 7 — Product resolver
- [x] Resolver + deterministic ambiguity detection (rejects "best Sony headphones"-style queries)

## Phase 8 — Research planner
- [x] Universal + category-specific dimensions (headphones/laptop/smartphone/kitchen_appliance + generic fallback)

## Phase 9-11 — Web / Reddit / YouTube research agents
- [x] SearchProvider (keyless DuckDuckGo default + serpapi/tavily/bing) / RedditProvider (public JSON) / YouTubeProvider (Data API v3 + transcripts), each with mock fixture fallback
- [x] LangGraph nodes per channel, graceful degradation on failure

## Phase 12-13 — Document/passage processing + evidence extraction
- [x] Chunking, grounding checks, evidence typing, source-independence clustering (n-gram/Jaccard)

## Phase 14 — pgvector integration
- [~] Embedding column + HNSW index (backend) done; AI-service-side dedup currently
      text-similarity based rather than a live pgvector query — see BUILD_STATUS.md
      "Recommended next steps"

## Phase 15-17 — Claims, conflict detection, verification
- [x] Claim generation with explicit SUPPORTS/CONTRADICTS/CONTEXTUALIZES relationships, conflicts preserved
- [x] 9-point verification checklist, deterministic confidence scoring

## Phase 18 — Report synthesis
- [x] Deterministic overall score/verdict/confidence from category scores, full report + sections

## Phase 19 — SSE progress pipeline
- [x] End-to-end event flow ai-service → backend internal API → Redis pub/sub → SSE → frontend, with replay for late subscribers

## Phase 20-21 — Frontend research + report UX
- [x] All routes (/, /research, /research/[id], /research/[id]/report, /login, /signup)
- [x] TanStack Query hooks, SSE client (EventSource + fetch-stream fallback), full progressive-disclosure report UI

## Phase 22 — Auth/security
- [x] Supabase JWT resource server path + documented dev-auth fallback with auto-provisioning, ownership enforcement

## Phase 23 — Testing/evaluation
- [x] Backend: 146 JUnit/Mockito/Spring-Boot-Test tests incl. Testcontainers E2E
- [x] AI service: 137 pytest tests + deterministic eval harness (grounding/citation/conflict checks) against golden fixture

## Phase 24 — Docker/documentation
- [x] Dockerfiles for all three services, docker-compose wiring (incl. frontend build args)
- [x] README/docs pass

## Phase 25 — Full end-to-end verification
- [x] Golden path (Sony WH-1000XM6) verified live through `docker compose up --build`:
      QUEUED→COMPLETED in ~5s, 12 sources / 77 evidence / 10 claims / 8 verified, full
      report with the mic indoor/outdoor conflict preserved, deterministic score/confidence.
      One real bug found and fixed (backend HTTP/2-over-plaintext vs. uvicorn) — see BUILD_STATUS.md.
      Also verified: ambiguous-query rejection, cross-user 404 ownership, SSE replay+relay.
- [x] BUILD_STATUS.md
