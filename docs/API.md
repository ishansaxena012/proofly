# Proofly API Contract

Base URL (public): `/api/v1`. All authenticated endpoints require a bearer token; backend
resolves it to a `users.id` and enforces ownership on every job/report/source/evidence
lookup (404, not 403, for jobs the caller doesn't own — don't leak existence).

## Public REST API

### `POST /api/v1/research`
Request: `{ "productQuery": string }`
Response `202`: `{ "researchJobId": uuid, "status": "QUEUED" }`
Errors: `400` invalid/empty query.

### `GET /api/v1/research/{id}`
Response `200`:
```json
{
  "id": "uuid",
  "status": "RESEARCHING",
  "currentStage": "RESEARCHING",
  "demoMode": true,
  "product": { "id": "uuid", "rawQuery": "...", "canonicalName": "...", "brand": "...", "category": "...", "model": "..." },
  "sourceCount": 12, "evidenceCount": 34, "claimCount": 9, "verifiedClaimCount": 7,
  "errorCode": null, "errorMessage": null,
  "createdAt": "...", "startedAt": "...", "completedAt": null
}
```

### `GET /api/v1/research/{id}/report`
`200` full report DTO (see below) once `COMPLETED`/`PARTIALLY_COMPLETED`; `409` otherwise
with `{ "status": "...", "errorCode": "INSUFFICIENT_DATA", "message": "...", "timestamp": "..." }`
(the standard error envelope plus a `status` field — there's no dedicated "not ready" code).

### `GET /api/v1/research/{id}/sources`
`200` list of `{ id, channel, url, title, sourceType, authorityScore, firstHand,
independenceGroupId, status }`. `failureReason` for a failed source is not exposed here —
it surfaces through the report's `CAVEATS` section instead.

### `GET /api/v1/research/{id}/evidence`
`200` list of `{ id, sourceId, topic, sentiment, evidenceType, strength, text }`, supports
`?topic=` filter.

### `GET /api/v1/research/{id}/events` (SSE)
`Content-Type: text/event-stream`. Replays persisted `research_events` for the job first
(so late subscribers/refreshes see full history), then streams live. Each SSE `event:`
name is the event type; `data:` is JSON `{ id, eventType, message, payload, createdAt }`
(`id` lets the client de-duplicate across replay/live overlap).

Browsers' native `EventSource` cannot send an `Authorization` header, so this endpoint
(only this one — regex-scoped so tokens don't leak into logs elsewhere) also accepts the
bearer credential as `?access_token={jwt-or-dev-token}`.

Event types (spec §24):
```
PRODUCT_IDENTIFIED, RESEARCH_STARTED, WEB_RESEARCH_COMPLETED, REDDIT_RESEARCH_COMPLETED,
YOUTUBE_RESEARCH_COMPLETED, EVIDENCE_EXTRACTION_STARTED, EVIDENCE_EXTRACTION_COMPLETED,
CLAIMS_GENERATED, VERIFICATION_STARTED, VERIFICATION_COMPLETED,
REPORT_GENERATION_STARTED, REPORT_COMPLETED, JOB_FAILED, JOB_PARTIALLY_COMPLETED
```

### `POST /api/v1/research/{id}/followup` (spec §40, evidence-grounded Q&A)
Request: `{ "question": string }`. Response `200`: `{ "answer": string, "citedEvidenceIds": [uuid] }`.
Backend proxies to AI service `POST /internal/v1/research/{id}/followup` with the job's
existing evidence/claims; never lets the LLM introduce new unsupported facts.

### Auth (as implemented)
The frontend uses Supabase Auth directly for login/signup/session when
`NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` are set, and backend validates
the Supabase-issued JWT (`JWT_ISSUER_URI` configured → OAuth2 resource server, JWKS
fetched lazily, optional `JWT_AUDIENCE` check). When Supabase Auth isn't configured on
either side, both fall back to a documented dev scheme: the frontend sends
`Authorization: Bearer dev-{userId}` where `userId` is a SHA-256-derived v4 UUID from the
user's (lowercased) email; the backend auto-provisions a `users` row the first time it
sees an unrecognized dev id. This path is loudly logged as dev-only — it identifies a
caller but does not authenticate them, and should never be enabled where
`JWT_ISSUER_URI` is set in a real deployment.

## Report DTO shape

```json
{
  "researchJobId": "uuid",
  "demoMode": true,
  "overallScore": 82,
  "verdict": "Recommended with caveats",
  "confidence": 0.74,
  "executiveSummary": "...",
  "categoryScores": [ { "category": "Sound Quality", "score": 88, "confidence": 0.8 } ],
  "keyStrengths": [ { "text": "...", "evidenceIds": ["uuid"] } ],
  "keyWeaknesses": [ { "text": "...", "evidenceIds": ["uuid"] } ],
  "keyFindings": [ { "text": "...", "claimId": "uuid" } ],
  "commonPraise": [ { "text": "...", "evidenceIds": ["uuid"] } ],
  "commonComplaints": [ { "text": "...", "evidenceIds": ["uuid"] } ],
  "conflicts": [
    {
      "topic": "Microphone quality",
      "positionA": { "text": "Good indoors", "evidenceIds": ["uuid"] },
      "positionB": { "text": "Poor outdoors", "evidenceIds": ["uuid"] },
      "explanation": "Context-dependent: indoor vs outdoor wind noise.",
      "resolved": false
    }
  ],
  "longTermOwnership": { "text": "...", "evidenceIds": ["uuid"] },
  "whoShouldBuy": ["..."],
  "whoShouldAvoid": ["..."],
  "caveats": ["YouTube research was unavailable for this run..."],
  "sources": [ { "id": "uuid", "url": "...", "title": "...", "sourceType": "...", "channel": "..." } ],
  "claims": [
    {
      "id": "uuid", "topic": "...", "statement": "...", "status": "SUPPORTED", "confidence": 0.8,
      "supportingEvidence": [ { "id": "uuid", "text": "...", "sourceId": "uuid" } ],
      "contradictingEvidence": [],
      "contextualisingEvidence": []
    }
  ],
  "generatedAt": "...",
  "version": 1
}
```

## Internal API (backend, called by ai-service; header `X-Internal-Key: {INTERNAL_API_KEY}`)

All internal callbacks are idempotent: upsert by the caller-supplied id, falling back to
`(researchJobId, url)` for sources without one yet.

- `POST /internal/v1/research/{id}/status` — `{ status, currentStage, errorCode?, errorMessage? }`
- `POST /internal/v1/research/{id}/product` — resolved product fields
- `POST /internal/v1/research/{id}/events` — `{ eventType, message, payload }`
- `POST /internal/v1/research/{id}/sources` — `{ "sources": [ research_sources fields ] }`
- `POST /internal/v1/research/{id}/evidence` — `{ "evidence": [ evidence fields ] }`.
  `evidence.passageId` is always `null` over the wire — the ai-service keeps
  documents/passages in-process and doesn't push them, so citation traceability in the
  report is `claim → evidence → source → URL`, not `→ passage →`.
- `POST /internal/v1/research/{id}/claims` — `{ "claims": [ claims fields ], "claimEvidence":
  [ { claimId, evidenceId, relationship } ] }` (nested `claims[].evidence` is also accepted)
- `POST /internal/v1/research/{id}/report` — the full Report DTO (below) plus a `"sections":
  [ { sectionType, title, content, orderIndex } ]` array for `report_sections`; finalizes
  the job. Echoed-back `researchJobId`/`demoMode`/`sources`/`claims` fields are accepted
  and ignored (backend already has its own copies).

## AI service API (backend → ai-service; header `X-Internal-Key`)

- `GET /health`
- `POST /internal/v1/research/execute` — `{ researchJobId, productQuery, demoMode }` → `202`
- `POST /internal/v1/research/{id}/followup` — `{ question, evidence[], claims[] }` → `{ answer, citedEvidenceIds }`
- `POST /internal/v1/research/{id}/cancel` — best-effort cancellation

## Error shape (all services)

```json
{ "errorCode": "INVALID_PRODUCT", "message": "...", "timestamp": "..." }
```
Codes: `SOURCE_FAILURE, AGENT_FAILURE, LLM_FAILURE, TIMEOUT, RATE_LIMIT, INVALID_PRODUCT,
INSUFFICIENT_DATA, NOT_FOUND, VALIDATION_ERROR, UNAUTHORIZED, FORBIDDEN`.
