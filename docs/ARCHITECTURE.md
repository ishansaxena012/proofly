# Proofly Architecture & Contracts

This is the binding contract between the three subsystems (frontend, backend, ai-service).
Any implementing agent/engineer must conform to this document; if something here proves
unworkable, adapt pragmatically but keep the shapes close and update this file.

## 1. Components

- **frontend/** — Next.js 14+ (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Query.
- **backend/** — Spring Boot 3.x, Java 21, Maven. System of record, public API, security,
  SSE, Redis-backed job dispatch queue.
- **ai-service/** — Python 3.12, FastAPI, LangGraph. Stateless-ish worker: given a job, it
  runs the research graph and streams results back to backend via internal HTTP callbacks.

## 2. Database schema (Flyway migrations, Supabase Postgres + pgvector)

All PKs are `uuid default gen_random_uuid()`. All tables have `created_at timestamptz
default now()`; mutable tables also have `updated_at timestamptz default now()`.

```sql
users (
  id uuid pk,
  email text unique not null,
  display_name text,
  created_at, updated_at
)

products (
  id uuid pk,
  raw_query text not null,
  canonical_name text,
  brand text,
  category text,
  model text,
  resolution_confidence numeric,
  created_at
)

research_jobs (
  id uuid pk,
  user_id uuid fk users,
  product_id uuid fk products,
  status text not null,        -- see State Machine below
  current_stage text,
  demo_mode boolean not null default false,
  error_code text,
  error_message text,
  source_count int default 0,
  evidence_count int default 0,
  claim_count int default 0,
  verified_claim_count int default 0,
  llm_call_count int default 0,
  started_at, completed_at,
  created_at, updated_at
)

research_events (
  id uuid pk,
  research_job_id uuid fk research_jobs,
  event_type text not null,    -- see SSE Events in API.md
  message text,
  payload jsonb,
  created_at
)  -- append-only log; also replayed to late SSE subscribers

research_sources (
  id uuid pk,
  research_job_id uuid fk research_jobs,
  channel text not null,       -- WEB | REDDIT | YOUTUBE
  url text not null,
  title text,
  source_type text,            -- OFFICIAL_DOC | PROFESSIONAL_REVIEW | USER_EXPERIENCE | FORUM_POST | VIDEO_REVIEW | GENERIC
  authority_score numeric,     -- 0..1
  first_hand boolean,
  independence_group_id uuid,  -- shared id => near-duplicate/syndicated cluster
  status text not null default 'FETCHED',  -- FETCHED | FAILED | SKIPPED
  failure_reason text,
  fetched_at, created_at
)

documents (
  id uuid pk,
  source_id uuid fk research_sources,
  raw_text text,
  content_hash text,
  token_count int,
  created_at
)

passages (
  id uuid pk,
  document_id uuid fk documents,
  text text not null,
  embedding vector(768),
  position int,
  created_at
)

evidence (
  id uuid pk,
  research_job_id uuid fk research_jobs,
  source_id uuid fk research_sources,
  passage_id uuid fk passages nullable,
  topic text not null,
  sentiment text,               -- POSITIVE | NEGATIVE | NEUTRAL | MIXED
  evidence_type text not null,  -- FACT | SPECIFICATION | EXPERT_OPINION | CUSTOMER_EXPERIENCE
                                 -- | REPEATED_PATTERN | ANECDOTE | COMPARISON | MEASUREMENT | CLAIM
  strength text,                -- STRONG | MODERATE | WEAK
  text text not null,
  created_at
)

claims (
  id uuid pk,
  research_job_id uuid fk research_jobs,
  topic text not null,
  statement text not null,
  status text not null,   -- SUPPORTED | PARTIALLY_SUPPORTED | CONTESTED | INSUFFICIENT_EVIDENCE
  confidence numeric,      -- 0..1
  created_at, updated_at
)

claim_evidence (
  id uuid pk,
  claim_id uuid fk claims,
  evidence_id uuid fk evidence,
  relationship text not null,  -- SUPPORTS | CONTRADICTS | CONTEXTUALIZES
  created_at
)

reports (
  id uuid pk,
  research_job_id uuid fk research_jobs unique,
  overall_score numeric,     -- 0..100, derived — never LLM-invented
  verdict text,
  confidence numeric,
  executive_summary text,
  generated_at,
  version int default 1,
  created_at
)

report_sections (
  id uuid pk,
  report_id uuid fk reports,
  section_type text not null,  -- EXECUTIVE_SUMMARY | CATEGORY_ANALYSIS | STRENGTHS | WEAKNESSES
                                -- | KEY_FINDINGS | COMMON_PRAISE | COMMON_COMPLAINTS | CONFLICTS
                                -- | LONG_TERM_OWNERSHIP | WHO_SHOULD_BUY | WHO_SHOULD_AVOID
                                -- | CAVEATS | SOURCES
  title text,
  content jsonb not null,
  order_index int,
  created_at
)
```

Indexes: FK columns, `research_jobs(user_id, status)`, `research_events(research_job_id,
created_at)`, `evidence(research_job_id, topic)`, ivfflat/hnsw index on `passages.embedding`.

## 3. Research job state machine

`CREATED → QUEUED → RUNNING → IDENTIFYING_PRODUCT → PLANNING_RESEARCH → RESEARCHING →
EXTRACTING_EVIDENCE → ANALYZING → VERIFYING → GENERATING_REPORT → COMPLETED`

Alternate terminal states: `PARTIALLY_COMPLETED`, `FAILED`, `CANCELLED`. Transitions are
persisted on `research_jobs` (`status`, `current_stage`, `updated_at`) and mirrored as
`research_events` rows.

## 4. Integration flow

1. Frontend `POST /api/v1/research {productQuery}` → backend creates `products` +
   `research_jobs` (status `CREATED`→`QUEUED`), pushes job id onto Redis list
   `proofly:research:queue`, returns `{researchJobId, status}` immediately.
2. A backend dispatcher (scheduled poller, bounded concurrency via
   `RESEARCH_MAX_CONCURRENT_JOBS`) pops queued job ids and calls the AI service:
   `POST {AI_SERVICE_URL}/internal/v1/research/execute` with
   `{researchJobId, productQuery, demoMode}`, auth header `X-Internal-Key:
   {INTERNAL_API_KEY}`. This call returns `202` immediately; the AI service runs the
   LangGraph pipeline as a background task.
3. As the pipeline progresses, the AI service calls back into backend's **internal API**
   (same `X-Internal-Key` header) to persist state — see `docs/API.md` §Internal API.
   Backend persists + appends a `research_events` row + publishes to Redis pub/sub channel
   `proofly:events:{jobId}`, which the SSE controller relays to subscribed clients.
4. Frontend polls `GET /api/v1/research/{id}` and/or subscribes to
   `GET /api/v1/research/{id}/events` (SSE) for live progress, then fetches
   `GET /api/v1/research/{id}/report` once `COMPLETED`/`PARTIALLY_COMPLETED`.

Redis is used for: the job queue (list), pub/sub fan-out for SSE, LangGraph checkpoint
storage keyed by job id (so a crashed run can resume from the last completed research
channel instead of restarting), and caching provider results by query hash (TTL) to avoid
duplicate search/Reddit/YouTube calls within a job.

## 5. Demo mode

`DEMO_MODE=true` (or missing provider credentials, per-provider) makes the AI service use
the mock `SearchProvider`/`RedditProvider`/`YouTubeProvider`/`LLMProvider` implementations,
which return deterministic fixture data from `ai-service/app/fixtures/` — notably the
golden-path fixture for **Sony WH-1000XM6**. Every `research_jobs.demo_mode` row and every
report visibly indicates when it was produced in demo mode. Demo mode must produce the
exact same evidence→claims→verification→report pipeline as live mode; only the source
providers differ.

## 6. Frontend routes

`/` (landing), `/research` (start a job), `/research/[id]` (live progress timeline),
`/research/[id]/report` (flagship report view). Auth pages `/login`, `/signup` if Supabase
Auth is wired; otherwise a minimal dev-only auth stub that still enforces ownership checks
server-side.
