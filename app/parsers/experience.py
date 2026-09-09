from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.dates import parse_date_range, strip_date_range
from app.parsers.support import all_lines, clean_line, section_lines
from app.schemas.candidate import ExperienceItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_AT = re.compile(r"\s+(?:at|@)\s+", re.I)
_EMPLOYMENT = [
    ("intern", "internship"),
    ("internship", "internship"),
    ("contract", "contract"),
    ("freelance", "freelance"),
    ("consultant", "consulting"),
    ("consulting", "consulting"),
    ("part-time", "part-time"),
    ("part time", "part-time"),
    ("remote", "remote"),
]


class ExperienceParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[ExperienceItem]:
        lines = section_lines(sections, "experience")
        if not lines:
            lines = _fallback_experience_lines(document)

        roles: list[ExperienceItem] = []
        current: ExperienceItem | None = None

        for line in lines:
            normalized = _clean_description_text(line)
            if not normalized:
                continue

            dates = parse_date_range(normalized)
            base = _clean_description_text(strip_date_range(normalized)) if dates else normalized

            if dates and base:
                if current and (current.job_title or current.company or current.description or current.start_date):
                    if not current.start_date and not current.end_date:
                        current.start_date = dates.start
                        current.end_date = dates.end
                        current.is_current = dates.is_current
                        current.confidence = max(current.confidence or 0.0, 0.82)
                        continue
                    roles.append(current)
                    current = None
                title, company = _split_title_company(base)
                current = ExperienceItem(
                    company=company,
                    job_title=title,
                    employment_type=_employment_type(base),
                    start_date=dates.start,
                    end_date=dates.end,
                    is_current=dates.is_current,
                    description=[],
                    confidence=0.82,
                )
                continue

            if dates and not base:
                if current and (current.job_title or current.company or current.description):
                    current.start_date = dates.start
                    current.end_date = dates.end
                    current.is_current = dates.is_current
                    current.confidence = max(current.confidence or 0.0, 0.82)
                    continue
                current = ExperienceItem(
                    company=None,
                    job_title=None,
                    employment_type=_employment_type(normalized),
                    start_date=dates.start,
                    end_date=dates.end,
                    is_current=dates.is_current,
                    description=[],
                    confidence=0.82,
                )
                continue

            if current is None and _looks_like_role_line(normalized):
                title, company = _split_title_company(normalized)
                current = ExperienceItem(
                    company=company,
                    job_title=title,
                    employment_type=_employment_type(normalized),
                    description=[],
                    confidence=0.72,
                )
                continue

            if current is not None and _looks_like_company_line(normalized):
                company = _extract_company(normalized)
                if company and not current.company:
                    current.company = company
                continue

            if current is not None:
                if _looks_like_role_line(normalized) and not current.job_title:
                    title, company = _split_title_company(normalized)
                    current.job_title = title
                    current.company = current.company or company
                    continue
                if normalized and not _looks_like_role_line(normalized):
                    current.description.append(normalized)
                    if not current.employment_type:
                        current.employment_type = _employment_type(normalized)
                    continue

            if current is not None and not _looks_like_role_line(normalized):
                current.description.append(normalized)

        if current and (current.job_title or current.company or current.start_date or current.description):
            roles.append(current)

        return [role for role in roles if role.company or role.job_title or role.start_date or role.description]


def _looks_like_role(text: str) -> bool:
    if not text or len(text) > 120:
        return False
    if text.startswith(("-", "•", "*")):
        return False
    return bool(_AT.search(text) or "," in text or " – " in text or " — " in text)


def _looks_like_role_line(text: str) -> bool:
    if not text or len(text) > 140:
        return False
    if text.startswith(("-", "•", "*", "●")):
        return False
    if re.search(r"\b(?:software|data|full|java|python|backend|frontend|lead|engineer|developer|analyst|manager|architect|trainer|consultant|specialist|associate|intern|executive)\b", text, re.I):
        return True
    return bool(_AT.search(text) or "," in text or " – " in text or " — " in text)


def _looks_like_company_line(text: str) -> bool:
    lower = text.lower()
    if any(term in lower for term in ("pvt", "ltd", "inc", "corp", "company", "technologies", "solutions", "group", "college")):
        return True
    return bool("|" in text and "," in text)


def _extract_company(text: str) -> str | None:
    cleaned = _clean_description_text(text)
    if not cleaned:
        return None
    if "|" in cleaned:
        left, right = cleaned.split("|", 1)
        return _clean(left) or _clean(right)
    return _clean(cleaned)


def _split_title_company(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    candidates = [part.strip() for part in re.split(r"\n+|\s*\|\s*|\s*(?:—|–|-)\s*", text) if part.strip()]
    if len(candidates) >= 2:
        title = candidates[0]
        company = None
        for candidate in candidates[1:]:
            if _looks_like_role(candidate) or re.fullmatch(r"\d{4}(?:\s*[–—-]\s*(?:Present|Current|\d{4}))?", candidate):
                continue
            company = candidate
            break
        if company:
            return _clean(title), _clean(company)
    at_split = _AT.split(text, maxsplit=1)
    if len(at_split) == 2:
        return _clean(at_split[0]), _clean(at_split[1])
    for sep in (" — ", " – ", " - "):
        if sep in text:
            left, right = text.split(sep, 1)
            return _clean(left), _clean(right)
    if "," in text:
        left, right = text.split(",", 1)
        return _clean(left), _clean(right)
    return _clean(text), None


def _clean(value: str) -> str | None:
    text = re.sub(r"\s+", " ", value).strip(" -,|•●▪◦·")
    return text or None


def _clean_description_text(text: str) -> str:
    return clean_line(text)


def _employment_type(text: str) -> str | None:
    lowered = text.lower()
    for needle, label in _EMPLOYMENT:
        if needle in lowered:
            return label
    return None


def _fallback_experience_lines(document: Document) -> list[str]:
    collect = False
    lines: list[str] = []
    for line in all_lines(document):
        lowered = line.lower()
        if lowered in {"education", "skills", "projects", "certifications"}:
            break
        if lowered in {"experience", "work experience", "professional experience"}:
            collect = True
            continue
        if collect:
            lines.append(line)
    return lines
