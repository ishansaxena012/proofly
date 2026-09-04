"""Request/response models for the AI service API (docs/API.md §AI service API)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ExecuteRequest(ApiModel):
    research_job_id: str
    product_query: str
    demo_mode: bool = False


class ExecuteResponse(ApiModel):
    research_job_id: str
    accepted: bool
    status: str


class FollowupEvidence(ApiModel):
    id: str
    text: str
    topic: str = ""
    source_id: str | None = None
    sentiment: str | None = None
    evidence_type: str | None = None
    strength: str | None = None


class FollowupClaim(ApiModel):
    id: str
    topic: str = ""
    statement: str = ""
    status: str | None = None
    confidence: float | None = None


class FollowupRequest(ApiModel):
    question: str
    evidence: list[FollowupEvidence] = Field(default_factory=list)
    claims: list[FollowupClaim] = Field(default_factory=list)


class FollowupResponse(ApiModel):
    answer: str
    cited_evidence_ids: list[str] = Field(default_factory=list)


class CancelResponse(ApiModel):
    research_job_id: str
    cancelled: bool
    message: str


class HealthResponse(ApiModel):
    status: str
    service: str
    demo_mode: bool
    active_jobs: int
    providers: dict[str, str]


class ErrorResponse(ApiModel):
    error_code: str
    message: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @staticmethod
    def payload(error_code: str, message: str) -> dict[str, Any]:
        return ErrorResponse(error_code=error_code, message=message).model_dump(by_alias=True)
