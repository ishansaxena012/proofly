"""Internal API consumed by the Spring Boot backend.

Every route requires ``X-Internal-Key: {INTERNAL_API_KEY}``; anything else gets a
403 with the shared error shape from docs/API.md.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.schemas import (
    CancelResponse,
    ErrorResponse,
    ExecuteRequest,
    ExecuteResponse,
    FollowupRequest,
    FollowupResponse,
)
from app.config import Settings, get_settings
from app.models.enums import ErrorCode, JobStatus
from app.providers.factory import build_providers
from app.services.followup import answer_followup
from app.services.runner import ResearchJobRunner

log = logging.getLogger(__name__)


async def require_internal_key(
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_internal_key or x_internal_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse.payload(
                ErrorCode.FORBIDDEN.value, "A valid X-Internal-Key header is required."
            ),
        )


router = APIRouter(
    prefix="/internal/v1/research",
    tags=["internal"],
    dependencies=[Depends(require_internal_key)],
)


def get_runner(request: Request) -> ResearchJobRunner:
    return request.app.state.runner


@router.post("/execute", status_code=status.HTTP_202_ACCEPTED, response_model=ExecuteResponse)
async def execute_research(
    payload: ExecuteRequest,
    runner: ResearchJobRunner = Depends(get_runner),
) -> ExecuteResponse:
    if not payload.research_job_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.payload(
                ErrorCode.VALIDATION_ERROR.value, "researchJobId is required."
            ),
        )
    if not payload.product_query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.payload(
                ErrorCode.VALIDATION_ERROR.value, "productQuery must not be empty."
            ),
        )

    accepted = runner.start(
        payload.research_job_id, payload.product_query.strip(), payload.demo_mode
    )
    return ExecuteResponse(
        research_job_id=payload.research_job_id,
        accepted=accepted,
        status=JobStatus.RUNNING.value if accepted else "ALREADY_RUNNING",
    )


@router.post("/{research_job_id}/followup", response_model=FollowupResponse)
async def followup(
    research_job_id: str,
    payload: FollowupRequest,
    settings: Settings = Depends(get_settings),
) -> FollowupResponse:
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.payload(
                ErrorCode.VALIDATION_ERROR.value, "question must not be empty."
            ),
        )

    providers = build_providers(settings)
    try:
        answer, cited = await answer_followup(
            providers.llm,
            payload.question,
            [item.model_dump() for item in payload.evidence],
            [claim.model_dump() for claim in payload.claims],
        )
    finally:
        await providers.aclose()

    log.info("follow-up answered for job %s citing %d evidence item(s)", research_job_id, len(cited))
    return FollowupResponse(answer=answer, cited_evidence_ids=cited)


@router.post("/{research_job_id}/cancel", response_model=CancelResponse)
async def cancel_research(
    research_job_id: str,
    runner: ResearchJobRunner = Depends(get_runner),
) -> CancelResponse:
    cancelled = runner.cancel(research_job_id)
    return CancelResponse(
        research_job_id=research_job_id,
        cancelled=cancelled,
        message=(
            "Cancellation requested."
            if cancelled
            else "No running job with that id; nothing to cancel."
        ),
    )
