from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.dates import DateSpan, parse_date_range, parse_date_token, strip_date_range
from app.parsers.support import clean_line, fallback_section_lines, section_lines
from app.schemas.candidate import ExperienceItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_AT = re.compile(r"\s+(?:at|@)\s+", re.I)
_BULLET_RAW = re.compile(r"^\s*(?:[\-*•●▪◦‣⁃]|\d+[.)])\s+")
_ENVIRONMENT = re.compile(r"(?i)^environment\s*:")
_PAREN_DATE = re.compile(r"\(([^)]{4,40})\)")
_TITLE_SUFFIX = re.compile(
    r"(?i)\s+(?P<title>(?:senior |junior |lead |staff |principal |associate )?"
    r"(?:java |python |full[\s-]*stack |software |web |frontend |backend )?"
    r"(?:developer|engineer|analyst|manager|architect|consultant|specialist|intern|lead))\s*$"
)
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
            lines = fallback_section_lines(document, "experience")

        roles: list[ExperienceItem] = []
        current: ExperienceItem | None = None
        expanded: list[str] = []
        for line in lines:
            env_body, role_tail = _split_environment_and_role(line)
            if env_body is not None:
                expanded.append(env_body)
                if role_tail:
                    expanded.append(role_tail)
                continue
            expanded.append(line)

        for line in expanded:
            if _ENVIRONMENT.match(line.strip()):
                if current is not None:
                    current.technologies = _techs(line)
                continue
            is_bullet = bool(_BULLET_RAW.match(line))
            normalized = _clean_description_text(line)
            if not normalized:
                continue

            dates = None if is_bullet else parse_date_range(normalized)
            if dates is None and not is_bullet:
                dates = _paren_or_single_date(normalized)
            base = _clean_description_text(strip_date_range(normalized)) if dates else normalized
            if dates:
                base = _strip_orphan_parens(base)

            if dates and base:
                title, company, location = _split_role_fields(base)
                looks_new = bool(title or company) and (
                    _looks_like_role_line(base) or bool(title and company)
                )
                if current and looks_new and (
                    current.job_title or current.company or current.description or current.start_date
                ):
                    roles.append(current)
                    current = None
                elif current and not looks_new and not current.start_date and not current.end_date:
                    current.start_date = dates.start
                    current.end_date = dates.end
                    current.is_current = dates.is_current
                    current.confidence = max(current.confidence or 0.0, 0.82)
                    continue
                if current is None:
                    current = ExperienceItem(
                        company=company,
                        job_title=title,
                        location=location,
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

            if is_bullet:
                if current is not None:
                    current.description.append(normalized)
                    if not current.employment_type:
                        current.employment_type = _employment_type(normalized)
                continue

            if current is None and _looks_like_role_line(normalized):
                title, company, location = _split_role_fields(normalized)
                current = ExperienceItem(
                    company=company,
                    job_title=title,
                    location=location,
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

            if current is not None and _looks_like_role_line(normalized):
                if not current.job_title:
                    title, company, location = _split_role_fields(normalized)
                    current.job_title = title
                    current.company = current.company or company
                    current.location = current.location or location
                    continue
                if current.company or current.description or current.start_date or current.end_date:
                    roles.append(current)
                    title, company, location = _split_role_fields(normalized)
                    current = ExperienceItem(
                        company=company,
                        job_title=title,
                        location=location,
                        employment_type=_employment_type(normalized),
                        description=[],
                        confidence=0.72,
                    )
                    continue

            if current is not None:
                current.description.append(normalized)
                if not current.employment_type:
                    current.employment_type = _employment_type(normalized)

        if current and (current.job_title or current.company or current.start_date or current.description):
            roles.append(current)

        merged = _merge_duplicate_roles(
            [role for role in roles if role.company or role.job_title or role.start_date or role.description]
        )
        return merged


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
    if re.search(
        r"\b(?:software|data|full|java|python|backend|frontend|lead|engineer|developer|"
        r"analyst|manager|architect|trainer|consultant|specialist|associate|intern|executive)\b",
        text,
        re.I,
    ):
        return True
    return bool(_AT.search(text) or "," in text or " – " in text or " — " in text)


def _looks_like_company_line(text: str) -> bool:
    lower = text.lower()
    if any(
        term in lower
        for term in ("pvt", "ltd", "inc", "corp", "company", "technologies", "solutions", "group", "college")
    ):
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


def _split_role_fields(text: str) -> tuple[str | None, str | None, str | None]:
    suffix = _TITLE_SUFFIX.search(text)
    if suffix and ("," in text or _AT.search(text)):
        title = _clean(suffix.group("title"))
        rest = text[: suffix.start()].strip(" ,-|")
        if "," in rest:
            left, right = rest.split(",", 1)
            return title, _clean(left), _clean(right)
        return title, _clean(rest), None
    if "," in text:
        left, right = text.split(",", 1)
        if _looks_like_location(right) and not _looks_like_role_line(left):
            return None, _clean(left), _clean(right)
    title, company = _split_title_company(text)
    location = None
    if company and "," in company:
        left, right = company.split(",", 1)
        if _looks_like_location(right):
            company = _clean(left)
            location = _clean(right)
    return title, company, location


def _split_title_company(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    candidates = [part.strip() for part in re.split(r"\n+|\s*\|\s*|\s*(?:—|–|-)\s*", text) if part.strip()]
    if len(candidates) >= 2:
        title = candidates[0]
        company = None
        for candidate in candidates[1:]:
            if _looks_like_role(candidate) or re.fullmatch(
                r"\d{4}(?:\s*[–—-]\s*(?:Present|Current|\d{4}))?", candidate
            ):
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


def _looks_like_location(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b(usa|united states|india|uk|canada|remote)\b", lowered):
        return True
    return bool(re.search(r"\b[A-Z]{2}\b", text) or "," in text)


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


def _paren_or_single_date(text: str):
    match = _PAREN_DATE.search(text)
    if not match:
        return None
    inner = match.group(1).strip()
    spanned = parse_date_range(inner)
    if spanned:
        return spanned
    token = parse_date_token(inner)
    if not token:
        return None
    return DateSpan(start=token, end=None, is_current=False, raw=match.group(0))


def _strip_orphan_parens(text: str) -> str:
    text = _PAREN_DATE.sub("", text)
    return re.sub(r"\(\s*\)", "", text).strip(" -,")


def _split_environment_and_role(line: str) -> tuple[str | None, str | None]:
    if not _ENVIRONMENT.match(line.strip()):
        return None, None
    dates = parse_date_range(line)
    if not dates or not dates.raw:
        return line, None
    idx = line.lower().rfind(dates.raw.lower())
    if idx < 0:
        return line, None
    before = line[:idx].rstrip(" ,")
    match = re.search(
        r"([A-Z][A-Za-z0-9.&']{1,40}),\s*([A-Za-z][A-Za-z. ]{1,40})$",
        before,
    )
    if not match:
        return line, None
    return before[: match.start()].rstrip(" ,"), line[match.start() :].strip()


def _techs(environment_line: str) -> list[str]:
    _, remainder = environment_line.split(":", 1) if ":" in environment_line else ("", environment_line)
    items: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;|]+", remainder):
        cleaned = part.strip(" -•*")
        if not cleaned or len(cleaned.split()) > 5:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(cleaned)
    return items


def _company_key(name: str | None) -> str:
    text = re.sub(r"\([^)]*\)", "", name or "")
    text = strip_date_range(text)
    return re.sub(r"\s+", " ", text).strip(" ,").lower()


def _merge_duplicate_roles(roles: list[ExperienceItem]) -> list[ExperienceItem]:
    merged: list[ExperienceItem] = []
    for role in roles:
        key = (_company_key(role.company), (role.job_title or "").lower())
        existing = None
        for item in merged:
            item_key = (_company_key(item.company), (item.job_title or "").lower())
            if key[0] and item_key[0] == key[0] and (not key[1] or not item_key[1] or key[1] == item_key[1]):
                existing = item
                break
        if existing is None:
            merged.append(role)
            continue
        if role.description and len(role.description) > len(existing.description):
            existing.description = role.description
        if role.technologies and not existing.technologies:
            existing.technologies = role.technologies
        if role.is_current or (role.start_date and not existing.start_date):
            if not existing.start_date and role.start_date:
                existing.start_date = role.start_date
            if role.end_date or role.is_current:
                existing.end_date = role.end_date
                existing.is_current = role.is_current
        elif not existing.end_date and (role.end_date or role.is_current):
            existing.end_date = role.end_date
            existing.is_current = role.is_current
        if role.location and not existing.location:
            existing.location = role.location
        if role.company and len(role.company) < len(existing.company or role.company):
            existing.company = role.company
        existing.confidence = max(existing.confidence or 0.0, role.confidence or 0.0)
    return merged
