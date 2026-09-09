from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import ResumeParserError
from app.core.logging import configure_logging, log_event
from app.core.versions import PARSER_VERSION, PHASE
from app.schemas.common import ErrorBody, ErrorResponse

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    log_event(
        logger,
        "application_started",
        parser_version=PARSER_VERSION,
        phase=PHASE,
        environment=settings.environment,
        llm_enabled=settings.llm_enabled,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Hybrid Resume Parser",
        version=PARSER_VERSION,
        description="Deterministic-first resume parsing with optional LLM fallback.",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )
    application.include_router(api_router, prefix="/api/v1")

    @application.exception_handler(ResumeParserError)
    async def handle_parser_error(_request: Request, exc: ResumeParserError) -> JSONResponse:
        log_event(logger, "parser_error", code=exc.code, http_status=exc.http_status)
        body = ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message))
        return JSONResponse(status_code=exc.http_status, content=body.model_dump())

    return application


app = create_app()
