from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.support import combined_text, section_lines
from app.schemas.candidate import SkillItem
from app.schemas.document import Document
from app.sections.base import DetectedSection
from app.taxonomy_data import skill_alias_map

_SPLIT = re.compile(r"[,;/|•\n]+")


class SkillsParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[SkillItem]:
        mapping = skill_alias_map()
        items: list[SkillItem] = []
        seen: set[str] = set()
        section_blob = combined_text(sections, "skills")
        tokens = _tokens(section_lines(sections, "skills"))
        for token in tokens:
            item = _map_token(token, mapping, source="taxonomy" if token.lower() in mapping else "rule")
            key = (item.normalized or item.raw).lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        # Taxonomy hits elsewhere in the document only if the alias appears as a whole token.
        if not items:
            for alias, (canonical, category) in mapping.items():
                if _whole_word(alias, document.plain_text()):
                    key = canonical.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(
                        SkillItem(
                            raw=alias,
                            normalized=canonical,
                            category=category,
                            confidence=0.72,
                            source="taxonomy",
                        )
                    )
        elif section_blob:
            for alias, (canonical, category) in mapping.items():
                if canonical.lower() in seen:
                    continue
                if _whole_word(alias, section_blob):
                    seen.add(canonical.lower())
                    items.append(
                        SkillItem(
                            raw=alias,
                            normalized=canonical,
                            category=category,
                            confidence=0.9,
                            source="taxonomy",
                        )
                    )
        return items


def _tokens(lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        parts = _SPLIT.split(line)
        for part in parts:
            cleaned = part.strip(" -•*")
            if cleaned:
                tokens.append(cleaned)
    return tokens


def _map_token(token: str, mapping: dict[str, tuple[str, str | None]], source: str) -> SkillItem:
    hit = mapping.get(token.lower())
    if hit:
        canonical, category = hit
        return SkillItem(
            raw=token,
            normalized=canonical,
            category=category,
            confidence=0.95,
            source="taxonomy",
        )
    return SkillItem(raw=token, normalized=token, category=None, confidence=0.7, source=source)


def _whole_word(alias: str, text: str) -> bool:
    return re.search(rf"(?i)\b{re.escape(alias)}\b", text) is not None
