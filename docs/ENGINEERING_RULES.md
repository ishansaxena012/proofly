# Proofly Engineering Rules

Proofly is an AI Product Research Agent: given one specific product, it autonomously
gathers evidence from multiple independent sources (web, Reddit, YouTube), extracts
structured evidence, generates claims, verifies them, preserves conflicts, and produces
a transparent, citation-backed report.

## Non-negotiable product rules

1. **Evidence is the foundation of truth.** Never go straight from web → LLM → answer.
   The pipeline is always `Sources → Documents/Passages → Evidence → Claims →
   Verification → Report`. Every claim in a report must be traceable to evidence, a
   passage, a source, and a URL.
2. **Never fabricate.** No invented sources, URLs, reviews, transcripts, statistics, or
   citations — ever, including in demo mode. Demo mode uses clearly-labeled deterministic
   fixtures, never data dressed up as live research.
3. **Conflicts are preserved, not averaged away.** Contradictory evidence must show up in
   the report as an explicit conflict with both sides and their sources, never silently
   resolved by majority vote.
4. **Confidence reflects evidence quality**, not LLM confidence. Low/duplicate/dependent
   evidence → low confidence. "Insufficient evidence" is a valid, correct outcome.
5. **One product, one job, one report.** No comparison shopping, no marketplace, no cart,
   no affiliate links, no personalized discovery engine.

## Architecture (do not deviate without strong reason)

```
Next.js (TS) ──REST+SSE──▶ Spring Boot (Java 21) ──▶ Redis (queue/cache/checkpoints)
                                   │
                                   ├──▶ Supabase Postgres (system of record, Flyway-migrated)
                                   ├──▶ Supabase pgvector (embeddings / semantic retrieval)
                                   └──HTTP (internal API)──▶ Python FastAPI + LangGraph
                                                                   │
                                                          Gemini (behind LLMProvider)
                                                          Search/Reddit/YouTube (behind
                                                          provider interfaces, mockable)
```

- **Spring Boot owns**: users, auth/ownership, products, research jobs, source/evidence/
  claim/report persistence, the public REST+SSE API, orchestration/dispatch to the AI
  service, Redis-backed job queue.
- **Python AI service owns**: product resolution, planning, research agents (web/Reddit/
  YouTube), evidence extraction, claim generation, conflict detection, verification,
  report synthesis, embeddings. It **pushes** results back to Spring via an internal
  callback API (see `docs/API.md`) — it does not own the database.
- Full contracts (DB schema, REST API, internal callback API, SSE events, DTOs) are in
  `docs/ARCHITECTURE.md` and `docs/API.md`. Treat those as the source of truth for
  cross-service integration — do not invent parallel conventions.

## Provider abstractions

- `LLMProvider` (generate / generateStructured / embed) — Gemini is the only real
  implementation; never call the Gemini SDK outside this boundary.
- `SearchProvider`, `RedditProvider`, `YouTubeProvider` — each has a mock/fixture
  implementation that is used whenever the corresponding API key is absent
  (`DEMO_MODE=true` or missing credentials). The rest of the pipeline must not know or
  care which implementation is active.

## Safety / cost limits

Configurable via env, not magic numbers: max queries, max sources, max pages/source, max
tokens, max LLM calls, max job duration. Individual source/channel failures must degrade
gracefully, not fail the whole job.

## Workflow rules for anyone working on this repo

- No `TODO: implement later` / `throw new UnsupportedOperationException()` /
  `pass` placeholders for core functionality.
- Backend tests: JUnit + Mockito + Spring Boot Test, no live network calls.
- AI service tests: pytest with mocked providers/fixtures, no live network calls.
- Run builds/tests/lint after each meaningful subsystem; fix failures before moving on.

## Common commands

```bash
# Everything (requires Docker)
docker compose up --build

# Backend
cd backend && ./mvnw spring-boot:run
cd backend && ./mvnw test

# AI service
cd ai-service && uvicorn app.main:app --reload --port 8000
cd ai-service && pytest

# Frontend
cd frontend && npm run dev
cd frontend && npm run build
```

See `docs/IMPLEMENTATION_PLAN.md` for phase-by-phase status and `BUILD_STATUS.md` for
the current state of the build.
