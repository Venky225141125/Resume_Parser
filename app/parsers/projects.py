from __future__ import annotations

from app.parsers.base import FieldParser
from app.parsers.dates import parse_date_range, strip_date_range
from app.parsers.support import clean_line, section_lines
from app.schemas.candidate import ProjectItem
from app.schemas.document import Document
from app.sections.base import DetectedSection
from app.taxonomy_data import skill_alias_map
import re


class ProjectParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[ProjectItem]:
        mapping = skill_alias_map()
        items: list[ProjectItem] = []
        current: ProjectItem | None = None
        for raw_line in section_lines(sections, "projects"):
            line = clean_line(raw_line)
            if not line:
                continue
            dates = parse_date_range(line)
            remainder = strip_date_range(line) if dates else line
            if current is None or _looks_like_title(remainder):
                if current:
                    items.append(current)
                current = ProjectItem(
                    name=remainder.strip(" -") or None,
                    description=[],
                    technologies=_techs(remainder, mapping),
                    url=_url(line),
                    start_date=dates.start if dates else None,
                    end_date=dates.end if dates else None,
                    confidence=0.7,
                )
                continue
            if current:
                current.description.append(remainder)
                current.technologies = _unique(current.technologies + _techs(remainder, mapping))
                if not current.url:
                    current.url = _url(line)
        if current:
            items.append(current)
        return [item for item in items if item.name]


def _looks_like_title(text: str) -> bool:
    return bool(text) and not text.startswith(("-", "•", "*")) and len(text) < 90


def _url(text: str) -> str | None:
    match = re.search(r"https?://[^\s)]+", text)
    return match.group(0).rstrip(".,") if match else None


def _techs(text: str, mapping: dict[str, tuple[str, str | None]]) -> list[str]:
    found: list[str] = []
    for alias, (canonical, _) in mapping.items():
        if re.search(rf"(?i)\b{re.escape(alias)}\b", text):
            found.append(canonical)
    return _unique(found)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
