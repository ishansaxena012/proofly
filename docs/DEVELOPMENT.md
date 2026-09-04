# Development Guide

## Prerequisites

- Docker + Docker Compose (recommended path)
- For non-Docker development: JDK 21, Node 20+, Python 3.12, a local Postgres with
  `pgvector` (or Docker just for that one container), Redis

## Fastest path: Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

This starts `postgres` (pgvector-enabled, standing in for Supabase locally — point
`SUPABASE_DB_URL`/`SUPABASE_DB_URL_PY` at a real Supabase project instead when you have
one), `redis`, `ai-service` (:8000), `backend` (:8080), `frontend` (:3000).

Then open http://localhost:3000, go to **Start Research**, enter `Sony WH-1000XM6`
(the golden-path fixture — `DEMO_MODE=true` by default so this runs with zero API keys),
and watch the pipeline run through to a full report.

## Running services individually

### Backend (Spring Boot)

```bash
cd backend
./mvnw spring-boot:run       # requires postgres + redis reachable per .env
./mvnw test                  # unit tests
./mvnw package                # full build incl. Testcontainers integration tests (needs Docker)
```
Swagger UI: http://localhost:8080/swagger-ui.html

### AI service (FastAPI)

```bash
cd ai-service
python -m venv .venv && . .venv/Scripts/activate   # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest                                # unit tests, fully mocked, no network
python -m eval.run_eval               # deterministic evaluation harness against the golden fixture
```
Requires Python 3.12 to match the Dockerfile/`pyproject.toml` (a newer interpreter will
mostly work but isn't the pinned target).

### Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local     # adjust if backend isn't on localhost:8080
npm run dev
npm run build && npm run typecheck && npm run lint
```

## Database migrations

Flyway runs automatically on backend startup against `SUPABASE_DB_URL`. To run migrations
against a fresh database manually: `cd backend && ./mvnw flyway:migrate`.

## Demo mode vs. live mode

`DEMO_MODE=true` (the `.env.example` default) makes the AI service use deterministic
fixture data for any provider whose credentials are absent — this is what makes the
system fully runnable and demoable with zero external API keys. Every job/report run in
this mode is marked `demoMode: true` end-to-end (job status, report DTO, and a visible
banner in the UI) so demo output is never mistaken for live research.

To go live: fill in `GEMINI_API_KEY` (required for real synthesis/verification) and any
subset of `SEARCH_API_KEY`/`REDDIT_CLIENT_ID`+`REDDIT_CLIENT_SECRET`/`YOUTUBE_API_KEY`.
Search and Reddit both have keyless "real" defaults (DuckDuckGo HTML search, Reddit's
public `search.json`) that work without credentials once `DEMO_MODE=false` — YouTube
requires `YOUTUBE_API_KEY`. Any channel still missing a required credential in live mode
reports itself unavailable and the report discloses that as a caveat, rather than
silently substituting fixture data.

## Testing

- Backend: `cd backend && ./mvnw test` (146 tests: unit + `@WebMvcTest`/`@DataJpaTest` +
  a full Testcontainers Postgres+Redis end-to-end API test). Some integration tests are
  skipped without Docker.
- AI service: `cd ai-service && pytest` (137 tests, fully mocked/offline) and
  `python -m eval.run_eval` (grounding/citation/conflict-preservation checks against the
  golden fixture).
- Frontend: `cd frontend && npm run build && npm run typecheck && npm run lint`.

## Troubleshooting

- **SSE stream cuts off immediately**: confirm you're on a build that includes the
  `dispatcherTypeMatchers(ASYNC, ERROR).permitAll()` security fix — earlier revisions
  truncated the stream because Spring Security re-authorized the async dispatch.
- **Testcontainers tests all skip silently**: Docker Engine 29+ needs
  `-Dapi.version=1.41` (already pinned in `backend/pom.xml`); override with
  `-Ddocker.api.version=` if your Engine version needs a different one.
- **`ai-service` checkpoint resume**: uses a custom Redis-backed checkpointer (plain
  Redis, not RediSearch) since `redis:7-alpine` lacks the modules LangGraph's official
  Redis saver needs.
