"""Canonicalize raw skill tokens against the skill taxonomy.

Extraction (app.parsers.skills) still owns *finding* candidate tokens —
tokenizing the Skills section, harvesting known-skill mentions elsewhere in
the resume, splitting "Environment:" lines. This module owns turning a raw
token into a SkillItem with its canonical name/category, and the label/noise
filtering that goes with that — so any future extraction source (e.g. an
LLM-extracted skill string) can be canonicalized the same way without
duplicating the taxonomy lookup logic.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.normalization.base import Normalizer
from app.schemas.candidate import SkillItem
from app.taxonomy_data import skill_alias_map

_CATEGORY_LABELS = {
    "languages",
    "programming languages",
    "tools",
    "databases",
    "database",
    "web servers",
    "web services",
    "methodologies",
    "operating systems",
    "frameworks",
    "libraries",
    "technologies",
    "environment",
    "technical skills",
    "core skills",
    "skills",
}
_NOISE_SKILLS = {
    "analysis",
    "design",
    "testing",
    "core",
    "data",
    "interface",
    "implementation",
    "development",
    "methodologies",
}


# \b is wrong at the edges of skill names: "C++" and "C#" end on a non-word
# character, so \b after them never matches and those skills could never be
# found. These boundaries treat +, # and . as part of a skill token instead.
_LEFT_BOUNDARY = r"(?<![A-Za-z0-9_#+.])"
_RIGHT_BOUNDARY = r"(?![A-Za-z0-9_#+])"


def _alias_pattern(alias: str) -> str:
    return rf"(?i){_LEFT_BOUNDARY}{re.escape(alias)}{_RIGHT_BOUNDARY}"


# Skill names carry punctuation that ordinary word tokenizers throw away:
# "C++", "C#", ".NET", "Node.js", "CI/CD", "PL/SQL".
_TOKEN = re.compile(r"[A-Za-z0-9.+#][A-Za-z0-9.+#/_-]*")


@lru_cache(maxsize=4)
def _max_alias_words(aliases: tuple[str, ...]) -> int:
    return max((len(alias.split()) for alias in aliases), default=1)


class SkillNormalizer(Normalizer):
    """Alias-map lookups and item-list cleanup for skills."""

    def __init__(self) -> None:
        self._mapping = skill_alias_map()

    @property
    def mapping(self) -> dict[str, tuple[str, str | None]]:
        return self._mapping

    def match_token(self, token: str) -> SkillItem:
        """Canonicalize a single raw token found during extraction."""
        hit = self._mapping.get(token.lower())
        compact = re.sub(r"[\s/_]+", "", token.lower())
        if not hit:
            hit = self._mapping.get(compact)
        if hit:
            canonical, category = hit
            return SkillItem(
                raw=token,
                normalized=canonical,
                category=category,
                confidence=0.95,
                source="taxonomy",
            )
        return SkillItem(raw=token, normalized=token, category=None, confidence=0.7, source="rule")

    def is_noise_or_label(self, text: str) -> bool:
        key = re.sub(r"\s+", " ", text.strip().lower().rstrip(":"))
        return key in _CATEGORY_LABELS or key in _NOISE_SKILLS

    def contains_alias(self, alias: str, text: str) -> bool:
        return re.search(_alias_pattern(alias), text) is not None

    def find_aliases(self, text: str) -> list[str]:
        """Every taxonomy alias named anywhere in `text`.

        Looks up n-grams of the document against the alias map rather than
        searching the document once per alias. Scanning per alias — or as one
        giant regex alternation — costs O(document x gazetteer), which took
        ~1.7s per resume once the gazetteer passed a few hundred entries.
        This is O(document) regardless of how large the gazetteer grows.
        """
        tokens = [token.rstrip(".,;:!?)") for token in _TOKEN.findall(text)]
        tokens = [token for token in tokens if token]
        width = _max_alias_words(tuple(sorted(self._mapping)))
        seen: set[str] = set()
        found: list[str] = []
        for start in range(len(tokens)):
            # Longest first, so "Spring Boot" is preferred over "Spring" and
            # "SQL Server" over "SQL" at the same position.
            for size in range(min(width, len(tokens) - start), 0, -1):
                candidate = " ".join(tokens[start : start + size]).lower()
                if candidate in self._mapping and candidate not in seen:
                    seen.add(candidate)
                    found.append(candidate)
                    break
        return found

    def normalize(self, items: list[SkillItem]) -> list[SkillItem]:
        """Idempotent cleanup pass: drop noise/category-label entries and
        canonicalize any item that arrived with only a raw value (e.g. from
        the LLM fallback) but wasn't matched against the taxonomy yet."""
        cleaned: list[SkillItem] = []
        seen: set[str] = set()
        for item in items:
            resolved = item
            if resolved.source not in {"taxonomy", "rule"}:
                resolved = self.match_token(resolved.raw)
            key = (resolved.normalized or resolved.raw).lower()
            if key in seen or self.is_noise_or_label(resolved.raw):
                continue
            seen.add(key)
            cleaned.append(resolved)
        return cleaned
