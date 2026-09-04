-- Proofly initial schema (docs/ARCHITECTURE.md §2)
-- System of record: Supabase Postgres + pgvector.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── users ────────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email        text        NOT NULL UNIQUE,
    display_name text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- ── products ─────────────────────────────────────────────────────────────────
CREATE TABLE products (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_query             text        NOT NULL,
    canonical_name        text,
    brand                 text,
    category              text,
    model                 text,
    resolution_confidence numeric,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT products_resolution_confidence_range
        CHECK (resolution_confidence IS NULL OR (resolution_confidence >= 0 AND resolution_confidence <= 1))
);

-- ── research_jobs ────────────────────────────────────────────────────────────
CREATE TABLE research_jobs (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id            uuid        REFERENCES products (id) ON DELETE SET NULL,
    status                text        NOT NULL,
    current_stage         text,
    demo_mode             boolean     NOT NULL DEFAULT false,
    error_code            text,
    error_message         text,
    source_count          int         NOT NULL DEFAULT 0,
    evidence_count        int         NOT NULL DEFAULT 0,
    claim_count           int         NOT NULL DEFAULT 0,
    verified_claim_count  int         NOT NULL DEFAULT 0,
    llm_call_count        int         NOT NULL DEFAULT 0,
    started_at            timestamptz,
    completed_at          timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT research_jobs_status_check CHECK (status IN (
        'CREATED', 'QUEUED', 'RUNNING', 'IDENTIFYING_PRODUCT', 'PLANNING_RESEARCH',
        'RESEARCHING', 'EXTRACTING_EVIDENCE', 'ANALYZING', 'VERIFYING',
        'GENERATING_REPORT', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'))
);

CREATE INDEX idx_research_jobs_user_status ON research_jobs (user_id, status);
CREATE INDEX idx_research_jobs_product_id ON research_jobs (product_id);
CREATE INDEX idx_research_jobs_created_at ON research_jobs (created_at DESC);

-- ── research_events (append-only progress log, replayed to SSE subscribers) ───
CREATE TABLE research_events (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id uuid        NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    event_type      text        NOT NULL,
    message         text,
    payload         jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_research_events_job_created ON research_events (research_job_id, created_at);

-- ── research_sources ─────────────────────────────────────────────────────────
CREATE TABLE research_sources (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id       uuid        NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    channel               text        NOT NULL,
    url                   text        NOT NULL,
    title                 text,
    source_type           text,
    authority_score       numeric,
    first_hand            boolean,
    independence_group_id uuid,
    status                text        NOT NULL DEFAULT 'FETCHED',
    failure_reason        text,
    fetched_at            timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT research_sources_channel_check CHECK (channel IN ('WEB', 'REDDIT', 'YOUTUBE')),
    CONSTRAINT research_sources_status_check CHECK (status IN ('FETCHED', 'FAILED', 'SKIPPED')),
    CONSTRAINT research_sources_type_check CHECK (source_type IS NULL OR source_type IN (
        'OFFICIAL_DOC', 'PROFESSIONAL_REVIEW', 'USER_EXPERIENCE', 'FORUM_POST',
        'VIDEO_REVIEW', 'GENERIC')),
    CONSTRAINT research_sources_authority_range
        CHECK (authority_score IS NULL OR (authority_score >= 0 AND authority_score <= 1)),
    CONSTRAINT research_sources_job_url_unique UNIQUE (research_job_id, url)
);

CREATE INDEX idx_research_sources_job ON research_sources (research_job_id);
CREATE INDEX idx_research_sources_independence_group ON research_sources (independence_group_id);

-- ── documents ────────────────────────────────────────────────────────────────
CREATE TABLE documents (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id    uuid        NOT NULL REFERENCES research_sources (id) ON DELETE CASCADE,
    raw_text     text,
    content_hash text,
    token_count  int,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_source ON documents (source_id);
CREATE INDEX idx_documents_content_hash ON documents (content_hash);

-- ── passages (pgvector embeddings) ───────────────────────────────────────────
CREATE TABLE passages (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid        NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    text        text        NOT NULL,
    embedding   vector(768),
    "position"  int,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_passages_document ON passages (document_id);

-- ── evidence ─────────────────────────────────────────────────────────────────
CREATE TABLE evidence (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id uuid        NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    source_id       uuid        NOT NULL REFERENCES research_sources (id) ON DELETE CASCADE,
    passage_id      uuid        REFERENCES passages (id) ON DELETE SET NULL,
    topic           text        NOT NULL,
    sentiment       text,
    evidence_type   text        NOT NULL,
    strength        text,
    text            text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT evidence_sentiment_check CHECK (sentiment IS NULL OR sentiment IN (
        'POSITIVE', 'NEGATIVE', 'NEUTRAL', 'MIXED')),
    CONSTRAINT evidence_type_check CHECK (evidence_type IN (
        'FACT', 'SPECIFICATION', 'EXPERT_OPINION', 'CUSTOMER_EXPERIENCE',
        'REPEATED_PATTERN', 'ANECDOTE', 'COMPARISON', 'MEASUREMENT', 'CLAIM')),
    CONSTRAINT evidence_strength_check CHECK (strength IS NULL OR strength IN (
        'STRONG', 'MODERATE', 'WEAK'))
);

CREATE INDEX idx_evidence_job_topic ON evidence (research_job_id, topic);
CREATE INDEX idx_evidence_source ON evidence (source_id);
CREATE INDEX idx_evidence_passage ON evidence (passage_id);

-- ── claims ───────────────────────────────────────────────────────────────────
CREATE TABLE claims (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id uuid        NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    topic           text        NOT NULL,
    statement       text        NOT NULL,
    status          text        NOT NULL,
    confidence      numeric,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT claims_status_check CHECK (status IN (
        'SUPPORTED', 'PARTIALLY_SUPPORTED', 'CONTESTED', 'INSUFFICIENT_EVIDENCE')),
    CONSTRAINT claims_confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX idx_claims_job_topic ON claims (research_job_id, topic);

-- ── claim_evidence ───────────────────────────────────────────────────────────
CREATE TABLE claim_evidence (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id     uuid        NOT NULL REFERENCES claims (id) ON DELETE CASCADE,
    evidence_id  uuid        NOT NULL REFERENCES evidence (id) ON DELETE CASCADE,
    relationship text        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT claim_evidence_relationship_check CHECK (relationship IN (
        'SUPPORTS', 'CONTRADICTS', 'CONTEXTUALIZES')),
    CONSTRAINT claim_evidence_unique UNIQUE (claim_id, evidence_id, relationship)
);

CREATE INDEX idx_claim_evidence_claim ON claim_evidence (claim_id);
CREATE INDEX idx_claim_evidence_evidence ON claim_evidence (evidence_id);

-- ── reports ──────────────────────────────────────────────────────────────────
CREATE TABLE reports (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id   uuid        NOT NULL UNIQUE REFERENCES research_jobs (id) ON DELETE CASCADE,
    overall_score     numeric,
    verdict           text,
    confidence        numeric,
    executive_summary text,
    generated_at      timestamptz,
    version           int         NOT NULL DEFAULT 1,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT reports_overall_score_range
        CHECK (overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)),
    CONSTRAINT reports_confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

-- ── report_sections ──────────────────────────────────────────────────────────
CREATE TABLE report_sections (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id    uuid        NOT NULL REFERENCES reports (id) ON DELETE CASCADE,
    section_type text        NOT NULL,
    title        text,
    content      jsonb       NOT NULL,
    order_index  int,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT report_sections_type_check CHECK (section_type IN (
        'EXECUTIVE_SUMMARY', 'CATEGORY_ANALYSIS', 'STRENGTHS', 'WEAKNESSES',
        'KEY_FINDINGS', 'COMMON_PRAISE', 'COMMON_COMPLAINTS', 'CONFLICTS',
        'LONG_TERM_OWNERSHIP', 'WHO_SHOULD_BUY', 'WHO_SHOULD_AVOID', 'CAVEATS', 'SOURCES'))
);

CREATE INDEX idx_report_sections_report ON report_sections (report_id, order_index);
