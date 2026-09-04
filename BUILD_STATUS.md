# Build Status

Last verified: 2026-09-04, full `docker compose up --build` stack, live golden-path run.

## Completed

**Architecture & contracts** — `docs/ENGINEERING_RULES.md`, `docs/ARCHITECTURE.md` (DB schema, state
machine, integration flow), `docs/API.md` (public REST, internal callback API, SSE, DTOs),
kept up to date with the real implementation's deviations.

**Database** — Flyway migrations for all 12 tables (`users`, `products`, `research_jobs`,
`research_events`, `research_sources`, `documents`, `passages` w/ pgvector, `evidence`,
`claims`, `claim_evidence`, `reports`, `report_sections`), FKs/constraints/indexes, HNSW
index on `passages.embedding`. Verified: migrates cleanly on a fresh database.

**Backend (Spring Boot 3.5 / Java 21)** — full public REST API, internal callback API,
Redis-backed job queue + bounded-concurrency dispatcher, SSE with replay + live relay via
Redis pub/sub, dev-auth (auto-provisioning) and Supabase-JWT resource-server auth paths,
server-side ownership enforcement (404 not 403), stale-job reaper, OpenAPI/Swagger. 146
tests (unit/slice/Testcontainers E2E) passing.

**AI service (FastAPI / LangGraph, Python 3.12)** — product resolver (rejects ambiguous
queries), dimension planner (headphones/laptop/smartphone/kitchen_appliance + generic
fallback), web/Reddit/YouTube research agents each with a real keyless/API-key
implementation and a deterministic mock, evidence extraction with grounding checks and
source-independence clustering, claim generation with explicit conflict preservation,
9-point verification checklist, deterministic report/score synthesis, Redis-backed
checkpointing, hard budget enforcement (queries/sources/pages/tokens/LLM-calls/duration).
Golden-path fixture: Sony WH-1000XM6 (11 sources, a genuine mic indoor-vs-outdoor
conflict, syndicated/manufacturer-derived near-duplicates). 137 pytest tests + a
deterministic eval harness (`python -m eval.run_eval`, 13/13 checks) passing.

**Frontend (Next.js 15 / TypeScript / Tailwind / shadcn/ui / TanStack Query)** — all
routes (`/`, `/research`, `/research/[id]`, `/research/[id]/report`, `/login`, `/signup`)
fully implemented against the documented contract: real pipeline-stage timeline (no fake
percentages), full progressive-disclosure report UI (finding → claim → evidence →
source → URL), conflicts shown as explicit unresolved disagreements, demo-mode banner,
loading/empty/error states including "backend unreachable". Clean `npm run build` /
`typecheck` / `lint`.

**Docker** — Dockerfiles for all three services, `docker-compose.yml` wiring
frontend/backend/ai-service/redis/postgres (pgvector image standing in for Supabase
locally), frontend build-args for `NEXT_PUBLIC_*`. **Verified live**: `docker compose up
--build` brings up all five containers healthy, and a real research job run through it
end-to-end — `POST /api/v1/research {"productQuery":"Sony WH-1000XM6"}` →
`QUEUED → RUNNING → ... → COMPLETED` in ~5s, 12 sources / 77 evidence / 10 claims / 8
verified, full report with a preserved conflict, deterministic 61/100 score at 0.84
confidence, every source URL honestly labelled `fixtures.proofly.invalid` /
`[DEMO FIXTURE]`. Also verified: ambiguous query (`"best Sony headphones"`) correctly
fails with `INVALID_PRODUCT` instead of guessing; cross-user job access returns `404`;
SSE stream replays and relays live events via `?access_token=`.

**One real bug found and fixed during this integration pass**: the backend's JDK
`HttpClient` defaulted to HTTP/2, which sends an `h2c` upgrade request over the plaintext
connection to the ai-service; uvicorn/h11 doesn't support that and rejected every dispatch
with a bare `400` before the request even reached FastAPI routing (`AGENT_FAILURE` after
3 retries). Fixed in `backend/src/main/java/com/proofly/backend/config/HttpClientConfig.java`
by pinning `HttpClient.Version.HTTP_1_1`. This is the kind of cross-service integration
bug unit tests on either side, in isolation, cannot catch — only a real end-to-end run
surfaces it, which is exactly what this verification pass was for.

## Partially completed / known limitations

- **pgvector semantic retrieval is not yet wired into the AI service's live query path.**
  The column, HNSW index, and embedding generation exist; the AI service currently does
  its near-duplicate/independence clustering with text-similarity (n-gram/Jaccard)
  instead of a pgvector similarity query, and doesn't push passages to the backend (see
  `docs/API.md` — `evidence.passageId` is always `null` over the wire, so citation
  traceability is `claim → evidence → source → URL`, not through a persisted passage).
  Functionally this doesn't degrade the product (independence detection still works,
  citations still resolve to a real source/URL), but "semantic evidence retrieval" as an
  explicit pgvector-backed feature is the most substantive spec item not fully realized.
- **Tomcat logs a recoverable `RecycleRequiredException`** when an SSE client disconnects
  abruptly mid-stream (observed by forcibly killing a `curl -N` connection) — Tomcat's own
  virtual-thread async-request recovery handles it (`"Encountered a non-recycled request
  and recycled it forcedly"`) and the server stays healthy, but it's noisy in logs and
  worth a closer look if it shows up under real load.
- **Live provider credentials are untested** (no API keys were available in this
  environment) — Gemini, real search/Reddit/YouTube paths are implemented and unit-tested
  against mocked SDK responses, but have not been exercised against the real APIs. The
  provider-boundary design means swapping in real keys shouldn't require code changes,
  but "shouldn't" isn't "verified."
- **Backend Testcontainers integration tests** require Docker with API version 1.41+
  (pinned in `pom.xml`); they ran successfully in this environment but will silently skip
  rather than fail on a Docker Engine that rejects that negotiation.
- Follow-up Q&A (`POST /api/v1/research/{id}/followup`) is implemented and grounded in
  existing evidence/claims, but was not exercised live in this verification pass beyond
  the AI service's own unit tests.

## External credentials required for live (non-demo) mode

None are required to run and demo Proofly — `DEMO_MODE=true` is the default and the
system is fully functional with zero external credentials. To go live:

- `GEMINI_API_KEY` — required for real LLM synthesis/verification (no live equivalent exists)
- `SEARCH_API_KEY` + `SEARCH_PROVIDER` — optional; web research has a keyless default (DuckDuckGo HTML)
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — optional; Reddit research has a keyless default (public `search.json`)
- `YOUTUBE_API_KEY` — required for real YouTube research (no keyless default)
- `SUPABASE_URL` / `SUPABASE_DB_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` — to point at a real Supabase project instead of the local pgvector-Postgres stand-in
- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` — to enable real Supabase Auth in the frontend instead of the dev-auth fallback

## How to run

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000 → Start Research → `Sony WH-1000XM6`. Runs fully in demo mode.

Non-Docker development, per-service commands, and troubleshooting:
see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Demo mode

`DEMO_MODE=true` (the `.env.example` default). Any provider whose credentials are absent
falls back to a deterministic fixture rather than fabricating data; the golden-path
fixture is Sony WH-1000XM6. `demoMode: true` is visible on the job status, the report
payload, and as a UI banner throughout. See `docs/DEVELOPMENT.md#demo-mode-vs-live-mode`.

## Tests

| Service  | Command | Result |
|----------|---------|--------|
| Backend  | `cd backend && ./mvnw test` | 146 passed |
| AI service | `cd ai-service && pytest` | 137 passed |
| AI service (eval) | `cd ai-service && python -m eval.run_eval` | 13/13 checks passed |
| Frontend | `cd frontend && npm run build && npm run typecheck && npm run lint` | clean |

## Recommended next steps

1. Wire the AI service's independence-clustering/dedup path to a real pgvector similarity
   query against `passages.embedding` (currently text-similarity-based) and push passages
   through the internal API so evidence citations can resolve to a stored passage, not
   just the source.
2. Exercise the live (non-mock) Gemini/search/Reddit/YouTube providers against real
   credentials at least once before treating them as production-ready — they're
   unit-tested but not integration-tested against the real third-party APIs.
3. Investigate the Tomcat `RecycleRequiredException` under a real abrupt-disconnect load
   test (many clients closing SSE connections mid-stream) even though it self-recovered
   here.
4. Add versioned report regeneration ("smart refresh" per the spec) — the data model
   supports it (`reports.version`) but there's no endpoint/flow that reuses existing
   evidence on a re-run yet.
