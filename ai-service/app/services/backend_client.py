"""Client for the Spring Boot internal callback API (docs/API.md §Internal API).

The AI service is not the system of record: it pushes every intermediate result
here. Backend callbacks are best-effort — a failed callback is logged and the job
continues, because losing a progress ping must never destroy an expensive run.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.models.domain import Claim, Evidence, ProductResolution, Report, ReportSection, Source
from app.models.enums import EventType, JobStatus

log = logging.getLogger(__name__)


class BackendClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self.failures: list[str] = []

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.backend_internal_url.rstrip("/"),
                timeout=self._settings.http_timeout_seconds,
                headers={
                    "X-Internal-Key": self._settings.internal_api_key,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _post(self, path: str, payload: dict[str, Any]) -> bool:
        try:
            client = await self._http()
            response = await client.post(path, json=payload)
            if response.status_code >= 400:
                message = f"{path} -> HTTP {response.status_code}"
                log.warning("backend callback failed: %s", message)
                self.failures.append(message)
                return False
            return True
        except Exception as exc:  # noqa: BLE001 - callbacks must never kill a job
            message = f"{path} -> {type(exc).__name__}: {exc}"
            log.warning("backend callback failed: %s", message)
            self.failures.append(message)
            return False

    # ── endpoints ──────────────────────────────────────────────────────────

    async def post_status(
        self,
        job_id: str,
        status: JobStatus,
        current_stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "status": status.value,
            "currentStage": current_stage or status.value,
        }
        if error_code:
            payload["errorCode"] = error_code
        if error_message:
            payload["errorMessage"] = error_message
        return await self._post(f"/internal/v1/research/{job_id}/status", payload)

    async def post_product(self, job_id: str, product: ProductResolution) -> bool:
        payload = {
            "rawQuery": product.raw_query,
            "canonicalName": product.canonical_name,
            "brand": product.brand,
            "category": product.category,
            "model": product.model,
            "resolutionConfidence": round(product.resolution_confidence, 4),
        }
        return await self._post(f"/internal/v1/research/{job_id}/product", payload)

    async def post_event(
        self,
        job_id: str,
        event_type: EventType,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        body = {
            "eventType": event_type.value,
            "message": message,
            "payload": payload or {},
        }
        return await self._post(f"/internal/v1/research/{job_id}/events", body)

    async def post_sources(self, job_id: str, sources: list[Source]) -> bool:
        if not sources:
            return True
        return await self._post(
            f"/internal/v1/research/{job_id}/sources",
            {"sources": [source.to_wire() for source in sources]},
        )

    async def post_evidence(self, job_id: str, evidence: list[Evidence]) -> bool:
        if not evidence:
            return True
        return await self._post(
            f"/internal/v1/research/{job_id}/evidence",
            {"evidence": [item.to_wire() for item in evidence]},
        )

    async def post_claims(self, job_id: str, claims: list[Claim]) -> bool:
        if not claims:
            return True
        claim_evidence = [
            {
                "claimId": claim.id,
                "evidenceId": link.evidence_id,
                "relationship": link.relationship.value,
            }
            for claim in claims
            for link in claim.links
        ]
        return await self._post(
            f"/internal/v1/research/{job_id}/claims",
            {
                "claims": [claim.to_wire() for claim in claims],
                "claimEvidence": claim_evidence,
            },
        )

    async def post_report(
        self, job_id: str, report: Report, sections: list[ReportSection]
    ) -> bool:
        payload = report.to_wire()
        payload["sections"] = [
            {
                "sectionType": section.section_type.value,
                "title": section.title,
                "content": section.content,
                "orderIndex": section.order_index,
            }
            for section in sections
        ]
        return await self._post(f"/internal/v1/research/{job_id}/report", payload)
