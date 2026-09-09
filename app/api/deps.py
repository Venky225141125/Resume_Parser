from collections.abc import Generator

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.llm.stub import DisabledLlmFallback
from app.pipeline.orchestrator import ParsePipeline


def settings_dep() -> Settings:
    return get_settings()


def pipeline_dep() -> Generator[ParsePipeline, None, None]:
    yield ParsePipeline()


def llm_dep(settings: Settings = Depends(settings_dep)) -> DisabledLlmFallback:
    return DisabledLlmFallback(settings)
