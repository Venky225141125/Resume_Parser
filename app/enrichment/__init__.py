"""Optional statistical enrichment that runs after the deterministic parsers."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.enrichment.base import ExtractedSpan, SkillExtractor
from app.enrichment.ner_skills import TransformerSkillExtractor

__all__ = [
    "ExtractedSpan",
    "SkillExtractor",
    "TransformerSkillExtractor",
    "get_skill_extractor",
]


@lru_cache(maxsize=1)
def get_skill_extractor() -> SkillExtractor | None:
    """The configured skill enricher, or None when enrichment is off.

    Cached because constructing the extractor is what eventually loads a
    several-hundred-megabyte model; one instance is shared for the process.
    Returns None rather than a no-op object so callers must decide
    explicitly what to do without one.
    """
    settings = get_settings()
    if not settings.skill_ner_enabled:
        return None
    return TransformerSkillExtractor(
        settings.skill_ner_model,
        min_score=settings.skill_ner_min_score,
        max_chars=settings.skill_ner_max_chars,
        device=settings.skill_ner_device,
    )


def clear_skill_extractor_cache() -> None:
    get_skill_extractor.cache_clear()
