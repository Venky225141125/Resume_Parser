from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.llm.stub import DisabledLlmFallback
from app.pipeline.orchestrator import ParsePipeline
from app.services.sqlite_store import SqliteResultStore
from app.services.store import ResultStore


def settings_dep() -> Settings:
    return get_settings()


def pipeline_dep() -> Generator[ParsePipeline, None, None]:
    yield ParsePipeline()


def llm_dep(settings: Settings = Depends(settings_dep)) -> DisabledLlmFallback:
    return DisabledLlmFallback(settings)


@lru_cache
def _cached_store(database_url: str) -> ResultStore:
    return SqliteResultStore(database_url)


def store_dep(settings: Settings = Depends(settings_dep)) -> ResultStore:
    return _cached_store(settings.database_url)
