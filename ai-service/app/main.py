"""Proofly AI service — FastAPI application.

Runs the LangGraph research pipeline and pushes results to the Spring Boot
backend's internal API. It is not the system of record.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.internal import router as internal_router
from app.api.schemas import ErrorResponse, HealthResponse
from app.config import get_settings
from app.models.enums import ErrorCode
from app.providers.factory import build_providers
from app.services.runner import ResearchJobRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("proofly.ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.runner = ResearchJobRunner(settings)
    log.info(
        "AI service starting (demo_mode=%s, backend=%s)",
        settings.demo_mode,
        settings.backend_internal_url,
    )
    try:
        yield
    finally:
        await app.state.runner.shutdown()
        log.info("AI service stopped")


app = FastAPI(
    title="Proofly AI Service",
    version="1.0.0",
    description="Product research pipeline: sources → evidence → claims → verification → report.",
    lifespan=lifespan,
)
app.include_router(internal_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    runner: ResearchJobRunner | None = getattr(request.app.state, "runner", None)
    providers = build_providers(settings)
    try:
        provider_names = {
            "llm": providers.llm.name,
            "search": providers.search.name,
            "reddit": providers.reddit.name,
            "youtube": providers.youtube.name,
        }
    finally:
        await providers.aclose()
    return HealthResponse(
        status="ok",
        service="proofly-ai-service",
        demo_mode=settings.demo_mode,
        active_jobs=len(runner.active_jobs) if runner else 0,
        providers=provider_names,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "errorCode" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    code = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
    }.get(exc.status_code, ErrorCode.AGENT_FAILURE)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse.payload(code.value, str(detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse.payload(ErrorCode.VALIDATION_ERROR.value, str(exc.errors())),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse.payload(
            ErrorCode.AGENT_FAILURE.value, f"{type(exc).__name__}: {exc}"
        ),
    )
