from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.dates import parse_date_range, parse_date_token
from app.parsers.support import all_lines, section_lines
from app.schemas.candidate import EducationItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_DEGREE = re.compile(
    r"(?P<raw>"
    r"bachelor(?:'s)?(?:\s+of\s+[\w\s]+)?"
    r"|master(?:'s)?(?:\s+of\s+[\w\s]+)?"
    r"|mba|ph\.?d\.?|doctorate"
    r"|associate(?:'s)?"
    r"|diploma"
    r"|high school"
    r"|b\.?\s*tech|m\.?\s*tech"
    r"|b\.?\s*e\.?|m\.?\s*e\.?"
    r"|b\.?\s*sc\.?|m\.?\s*sc\.?"
    r"|bca|mca"
    r")",
    re.I,
)

_DEGREE_NORM = [
    (re.compile(r"ph\.?d|doctorate", re.I), "PhD"),
    (re.compile(r"\bmba\b", re.I), "MBA"),
    (re.compile(r"master(?:'s)?", re.I), "Master's"),
    (re.compile(r"bachelor(?:'s)?", re.I), "Bachelor's"),
    (re.compile(r"b\.?\s*tech", re.I), "B.Tech"),
    (re.compile(r"m\.?\s*tech", re.I), "M.Tech"),
    (re.compile(r"b\.?\s*e\.?\b", re.I), "B.E."),
    (re.compile(r"m\.?\s*e\.?\b", re.I), "M.E."),
    (re.compile(r"b\.?\s*sc", re.I), "B.Sc"),
    (re.compile(r"m\.?\s*sc", re.I), "M.Sc"),
    (re.compile(r"\bbca\b", re.I), "BCA"),
    (re.compile(r"\bmca\b", re.I), "MCA"),
    (re.compile(r"associate", re.I), "Associate"),
    (re.compile(r"diploma", re.I), "Diploma"),
    (re.compile(r"high school", re.I), "High School"),
]

_INSTITUTION = re.compile(
    r"(?P<inst>(?:[A-Z][\w.&'\-]+(?:\s+[A-Z][\w.&'\-]+)*)\s+"
    r"(?:University|College|Institute|School|Academy))",
)

_GPA = re.compile(r"(?:gpa|cgpa)\s*[:=]?\s*(\d+(?:\.\d+)?)", re.I)
_FIELD = re.compile(
    r"(?:in|of)\s+([A-Za-z][A-Za-z\s&/]+)$",
    re.I,
)


class EducationParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[EducationItem]:
        lines = section_lines(sections, "education")
        if not lines:
            lines = _fallback_lines(document, "education")
        items: list[EducationItem] = []
        current: EducationItem | None = None
        for line in lines:
            degree_match = _DEGREE.search(line)
            inst_match = _INSTITUTION.search(line)
            dates = parse_date_range(line)
            year = None
            if not dates:
                single = re.search(r"\b((?:19|20)\d{2})\b", line)
                year = single.group(1) if single else None
            if degree_match or inst_match or dates or (year and _DEGREE.search(line)):
                if current:
                    items.append(current)
                degree_raw = degree_match.group("raw").strip() if degree_match else None
                field = None
                if degree_match:
                    field_match = _FIELD.search(line[degree_match.end() :])
                    if field_match:
                        field = field_match.group(1).strip(" ,")
                    elif "computer science" in line.lower():
                        field = "Computer Science"
                gpa_match = _GPA.search(line)
                current = EducationItem(
                    institution=_clean_institution(inst_match.group("inst") if inst_match else _institution_fallback(line)),
                    degree=degree_raw,
                    degree_normalized=_normalize_degree(degree_raw) if degree_raw else None,
                    field_of_study=field,
                    start_date=dates.start if dates else None,
                    end_date=dates.end if dates else year,
                    graduation_date=(dates.end if dates and not dates.is_current else None) or year,
                    gpa=gpa_match.group(1) if gpa_match else None,
                    confidence=0.8 if degree_raw or inst_match else 0.6,
                )
                continue
            if current:
                if not current.institution:
                    current.institution = _institution_fallback(line)
                elif line not in (current.degree or ""):
                    current.specialization = line
        if current:
            items.append(current)
        return [item for item in items if item.institution or item.degree]


def _normalize_degree(raw: str) -> str:
    for pattern, label in _DEGREE_NORM:
        if pattern.search(raw):
            return label
    return raw


def _clean_institution(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip(" ,;-")


def _institution_fallback(line: str) -> str | None:
    if re.search(r"university|college|institute|school", line, re.I):
        return strip_dates(line)
    return None


def strip_dates(line: str) -> str:
    text = re.sub(r"\b((?:19|20)\d{2})\b", "", line)
    text = re.sub(r"[,;]\s*$", "", text)
    return text.strip(" ,;-")


def _fallback_lines(document: Document, heading: str) -> list[str]:
    collect = False
    lines: list[str] = []
    for line in all_lines(document):
        lowered = line.lower()
        if lowered in {"experience", "skills", "projects", "certifications"} and collect:
            break
        if lowered == heading or lowered.startswith(heading + " "):
            collect = True
            continue
        if collect:
            lines.append(line)
    return lines
