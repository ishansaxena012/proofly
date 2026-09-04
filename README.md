# Proofly

**Proofly is an AI product research agent.** Give it one specific product — not "best
headphones," but "Sony WH-1000XM6" — and it autonomously gathers evidence from
independent sources (web, Reddit, YouTube), extracts structured evidence, generates
claims, verifies them, preserves genuine disagreement between sources, and produces a
transparent, citation-backed report you can actually audit. 

It is deliberately **not**: a shopping marketplace, a price-comparison tool, a chatbot, or
a personalized recommendation engine. One product, one research job, one report.

## Why it's different from "ask an LLM"

Most AI shopping tools go straight from a web search to an LLM answer. Proofly doesn't:

```
Sources → Documents/Passages → Evidence → Claims → Verification → Report
```

Every conclusion in the final report is traceable back through a claim, to the evidence
that supports (or contradicts) it, to the passage it came from, to the source and its
URL. Conflicting evidence — "the mic is great indoors" vs. "the mic is bad outdoors" — is
preserved as an explicit, explained disagreement, never quietly averaged into a fake
consensus. Confidence reflects the quality and independence of the evidence, not the
LLM's tone; "insufficient evidence" is a valid and honest outcome.

## Architecture

```
Next.js (TS) ──REST + SSE──▶ Spring Boot (Java 21) ──▶ Redis (queue / cache / checkpoints)
                                    │
                                    ├──▶ Supabase Postgres + pgvector (system of record)
                                    └──HTTP (internal API)──▶ Python FastAPI + LangGraph
                                                                    │
                                                          Gemini (behind LLMProvider)
                                                          Web / Reddit / YouTube
                                                          (behind provider interfaces)
```

- **Frontend** — Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Query.
- **Backend** — Spring Boot 3.5 / Java 21: the system of record, public REST + SSE API,
  auth/ownership, the Redis-backed research job queue and dispatcher.
- **AI service** — Python 3.12 / FastAPI / LangGraph: product resolution, planning,
  research agents (web/Reddit/YouTube), evidence extraction, claim generation, conflict
  detection, verification, report synthesis — pushed back to the backend via an internal
  callback API rather than owning the database itself.
- **Supabase** — Postgres (system of record, Flyway-migrated) + pgvector (semantic
  retrieval / near-duplicate detection). Locally, a plain `postgres` container with the
  pgvector extension stands in so the whole stack runs without a real Supabase project.
- **Redis** — job queue, SSE pub/sub fan-out, LangGraph checkpointing, provider-result
  caching.

Full contracts (DB schema, REST/SSE/internal API shapes, state machine) live in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/API.md`](docs/API.md).

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000, click **Start Research**, enter `Sony WH-1000XM6` (the
golden-path fixture — this runs fully in demo mode with zero API keys since
`DEMO_MODE=true` by default), and watch it go from product resolution through research,
evidence extraction, verification, to a full report.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for running each service individually,
and [`.env.example`](.env.example) for every environment variable.

## Demo mode vs. live mode

Proofly is designed to be fully demoable with no external credentials: any provider
(search, Reddit, YouTube, Gemini) whose credentials are absent falls back to a
deterministic, clearly-labeled fixture, never to fabricated data pretending to be live
research. `demoMode: true` is visible end-to-end — job status, report payload, and a
banner in the UI. Add `GEMINI_API_KEY` and any provider keys in `.env` to go live; see
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md#demo-mode-vs-live-mode).

## Research flow

```
Enter product → Product resolution (rejects ambiguous queries) → Research planning
   → Web / Reddit / YouTube research (parallel, degrade gracefully on failure)
   → Evidence extraction (typed, source-independence-aware)
   → Claim generation (conflicts preserved) → Verification → Report synthesis
```

Progress streams live over SSE as real pipeline stages (`PRODUCT_IDENTIFIED`,
`WEB_RESEARCH_COMPLETED`, `CLAIMS_GENERATED`, `VERIFICATION_COMPLETED`, ...) — never a
fake percentage bar.

## Testing

- Backend: `cd backend && ./mvnw test` — 146 tests (unit, slice, and a full
  Testcontainers Postgres+Redis end-to-end API test).
- AI service: `cd ai-service && pytest` — 137 tests, fully mocked/offline, plus
  `python -m eval.run_eval`, a deterministic evaluation harness checking grounding,
  citation correctness, and conflict preservation against the golden fixture.
- Frontend: `cd frontend && npm run build && npm run typecheck && npm run lint`.

## Limitations / MVP boundaries

No shopping cart, checkout, affiliate links, multi-product comparison, personalized
discovery, browser extension, or mobile app — by design. See
[`BUILD_STATUS.md`](BUILD_STATUS.md) for the current, honest state of the implementation
and known limitations. It is cool tho. 

## Docs

- [`docs/ENGINEERING_RULES.md`](docs/ENGINEERING_RULES.md) — engineering rules and non-negotiables
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — schema, state machine, integration flow
- [`docs/API.md`](docs/API.md) — full REST/SSE/internal API contract
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — local dev, testing, troubleshooting
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — phase-by-phase status
- [`BUILD_STATUS.md`](BUILD_STATUS.md) — what's built, what's not, how to run it
