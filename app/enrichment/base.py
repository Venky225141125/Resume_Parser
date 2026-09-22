"""Optional layer-3 enrichment: statistical extractors that run *after* the
deterministic parsers and only add what those could not find.

The contract is deliberately narrow. An enricher receives plain text and
returns spans it believes are skills; it never sees the parsed candidate and
can never remove or overwrite a deterministic result. That keeps the default
path fully explainable and makes the enricher genuinely optional — if it is
disabled, uninstalled or broken, the parse is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExtractedSpan:
    """A span an enricher believes names a skill, with the model's score."""

    text: str
    score: float


@runtime_checkable
class SkillExtractor(Protocol):
    """Finds skill mentions in free text.

    Implementations must never raise: a model that fails to load or fails on
    an input returns an empty list, so enrichment degrades to the
    deterministic result rather than failing the request.
    """

    @property
    def name(self) -> str:
        """Identifier recorded as the `source` of anything this adds."""

    def available(self) -> bool:
        """False when the backing model or its dependencies are missing."""

    def extract(self, text: str) -> list[ExtractedSpan]:
        ...
