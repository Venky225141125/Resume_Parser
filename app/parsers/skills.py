from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.support import combined_text, section_lines, split_label_prefix
from app.schemas.candidate import SkillItem
from app.schemas.document import Document
from app.sections.base import DetectedSection
from app.taxonomy_data import skill_alias_map

_SPLIT = re.compile(r"[,;|•●\n]+")
_MAX_SKILL_WORDS = 4
_SKILL_SECTIONS = ("skills", "summary", "experience", "projects")
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


class SkillsParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[SkillItem]:
        mapping = skill_alias_map()
        items: list[SkillItem] = []
        seen: set[str] = set()

        for token in _tokens(section_lines(sections, "skills")):
            item = _map_token(token, mapping)
            _add(items, seen, item)

        section_blob = combined_text(sections, "skills")
        if section_blob:
            for alias, (canonical, category) in mapping.items():
                if canonical.lower() in seen:
                    continue
                if _whole_word(alias, section_blob):
                    _add(
                        items,
                        seen,
                        SkillItem(
                            raw=alias,
                            normalized=canonical,
                            category=category,
                            confidence=0.9,
                            source="taxonomy",
                        ),
                    )

        # Always harvest taxonomy hits from the whole resume so skills used
        # only in experience / summary / environment lines are not dropped
        # just because a short ATS "Skills" block already produced items.
        blob = document.plain_text()
        for alias, (canonical, category) in mapping.items():
            if canonical.lower() in seen:
                continue
            if _whole_word(alias, blob):
                _add(
                    items,
                    seen,
                    SkillItem(
                        raw=alias,
                        normalized=canonical,
                        category=category,
                        confidence=0.78,
                        source="taxonomy",
                    ),
                )

        for line in section_lines(sections, *_SKILL_SECTIONS):
            if not line.lower().startswith("environment:"):
                continue
            _, remainder = split_label_prefix(line)
            for token in _SPLIT.split(remainder):
                cleaned = token.strip(" -•*")
                if not cleaned:
                    continue
                _add(items, seen, _map_token(cleaned, mapping))

        return items


def _add(items: list[SkillItem], seen: set[str], item: SkillItem) -> None:
    key = (item.normalized or item.raw).lower()
    if key in seen or key in _NOISE_SKILLS or key in _CATEGORY_LABELS:
        return
    if _is_category_label(item.raw):
        return
    seen.add(key)
    items.append(item)


def _tokens(lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        _, remainder = split_label_prefix(line)
        if _is_category_label(remainder):
            continue
        parts = _SPLIT.split(remainder)
        for part in parts:
            cleaned = part.strip(" -•*")
            if not cleaned or _is_category_label(cleaned):
                continue
            if len(cleaned.split()) > _MAX_SKILL_WORDS:
                continue
            tokens.append(cleaned)
    return tokens


def _is_category_label(text: str) -> bool:
    return re.sub(r"\s+", " ", text.strip().lower().rstrip(":")) in _CATEGORY_LABELS


def _map_token(token: str, mapping: dict[str, tuple[str, str | None]]) -> SkillItem:
    hit = mapping.get(token.lower())
    compact = re.sub(r"[\s/_]+", "", token.lower())
    if not hit:
        hit = mapping.get(compact)
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


def _whole_word(alias: str, text: str) -> bool:
    return re.search(rf"(?i)\b{re.escape(alias)}\b", text) is not None
