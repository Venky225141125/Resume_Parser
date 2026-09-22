from __future__ import annotations

import re

from app.normalization.location import is_state_or_country, is_us_state
from app.parsers.base import FieldParser
from app.parsers.dates import DateSpan, parse_date_range, parse_date_token, strip_date_range
from app.parsers.support import (
    clean_line,
    embedded_project_name,
    fallback_section_lines,
    is_project_metadata,
    section_lines,
    split_label_prefix,
)
from app.schemas.candidate import ExperienceItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_AT = re.compile(r"\s+(?:at|@)\s+", re.I)
_BULLET_RAW = re.compile(r"^\s*(?:[\-*•●▪◦‣⁃]|\d+[.)])\s+")
_ENVIRONMENT = re.compile(r"(?i)^environment\s*:")
_ROLE_LABEL = re.compile(r"(?i)^(?:role|position|designation|job\s+title|title)\s*[:\-]\s*")
# Lines introduced by these labels describe the work, not the employer, and
# must never be mistaken for the company line beneath a role header.
_NON_COMPANY_LABEL = re.compile(
    r"(?i)^(?:description|responsibilit(?:y|ies)|environment|technolog(?:y|ies)|tools|"
    r"project|summary|duties|overview|objective|highlights|achievements)\s*[:\-]"
)
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
        in_project = False
        pending_dates: DateSpan | None = None
        expanded: list[str] = []
        for line in lines:
            env_body, role_tail = _split_environment_and_role(line)
            if env_body is not None:
                expanded.append(env_body)
                if role_tail:
                    expanded.append(role_tail)
                continue
            expanded.append(line)

        date_anchored = _is_date_anchored(expanded)

        for index, line in enumerate(expanded):
            if _ENVIRONMENT.match(line.strip()):
                if current is not None:
                    current.technologies = _techs(line)
                continue
            is_bullet = bool(_BULLET_RAW.match(line))
            normalized = _clean_description_text(line)
            if not normalized:
                continue
            # Which of the three header layouts a line belongs to can only be
            # told by looking at the line after it: "dates / header", "title /
            # company + dates", or everything on one line.
            next_line = _next_meaningful(expanded, index)
            if not is_bullet:
                # A "Key Project: X" block is work carried out inside the role
                # above it. It has its own role and stack but never its own
                # employer, so it opens an entry that inherits one.
                project_name = embedded_project_name(normalized)
                if project_name:
                    if current is not None and (
                        current.job_title or current.company or current.description or current.start_date
                    ):
                        roles.append(current)
                    current = ExperienceItem(
                        # Every entry is named by its own heading. Borrowing
                        # the enclosing role's employer put the previous
                        # entry's company on this one, which the resume never
                        # claims for it.
                        company=None,
                        job_title=project_name,
                        location=None,
                        description=[],
                        confidence=0.7,
                    )
                    in_project = True
                    continue
                if in_project and is_project_metadata(normalized):
                    _apply_project_metadata(current, normalized)
                    continue
                # "Role: Senior Software Engineer" — an explicit field label,
                # which belongs to the layout rather than to the job title.
                normalized = _ROLE_LABEL.sub("", normalized, count=1).strip() or normalized

            dates = None if is_bullet else parse_date_range(normalized)
            if dates is None and not is_bullet:
                dates = _paren_or_single_date(normalized)
            base = _clean_description_text(strip_date_range(normalized)) if dates else normalized
            if dates:
                base = _strip_orphan_parens(base)

            if dates and base:
                title, company, location = _split_role_fields(base)
                columns = _column_role_fields(line)
                if columns:
                    # The layout drew these boundaries explicitly, which beats
                    # inferring them from punctuation in the collapsed text.
                    col_title, col_company, col_location = columns
                    title = title or col_title
                    company = col_company or company
                    location = col_location or location
                looks_new = bool(title or company) and (
                    _looks_like_role_line(base) or bool(title and company)
                )
                if (
                    date_anchored
                    and current is not None
                    and (in_project or current.start_date or current.end_date)
                    and _header_like(base)
                ):
                    # In a date-anchored document every job header carries its
                    # own range, so a second range on a header-shaped line means
                    # a second job — whatever is left of the line after the
                    # dates are stripped. "Founder" alone parses as neither a
                    # "Title, Company" pair nor a recognized role noun, and its
                    # dates used to be silently absorbed by the previous entry.
                    looks_new = True
                # "Clinical Therapist" on one line, "Orlando Recovery Ctr -
                # Orlando, FL  August 2020 to Present" on the next: the title
                # sits *above* its company/date line. The entry opened by the
                # title is still empty, so this line completes it rather than
                # starting a second job.
                fresh_title_only = bool(
                    current is not None
                    and current.job_title
                    and not current.company
                    and not current.start_date
                    and not current.end_date
                    and not current.description
                )
                if fresh_title_only and (title is None or not _header_like(base)):
                    current.start_date = dates.start
                    current.end_date = dates.end
                    current.is_current = dates.is_current
                    if _header_like(base):
                        current.company = current.company or company
                        current.location = current.location or location
                    else:
                        # Prose glued onto the date line is this job's work.
                        current.description.append(base)
                    current.confidence = max(current.confidence or 0.0, 0.82)
                    continue
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
                    in_project = False
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
                if _is_strong_role_header(next_line or ""):
                    # "AUGUST 2018 - PRESENT" / "QA AUTOMATION ENGINEER,
                    # Alliance Tek Solutions": the range announces the job
                    # below it, so it must not be attached to the job above.
                    pending_dates = dates
                    continue
                if current and (current.job_title or current.company or current.description):
                    current.start_date = dates.start
                    current.end_date = dates.end
                    current.is_current = dates.is_current
                    current.confidence = max(current.confidence or 0.0, 0.82)
                    continue
                in_project = False
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

            # Some resumes put the date range on its own line *above* the
            # role header rather than beside or below it. Held here so it
            # lands on the job it announces instead of the one above it.
            partial = _partial_date_line(normalized)
            if partial is not None:
                pending_dates = partial
                continue

            if current is None and _looks_like_role_line(normalized):
                in_project = False
                title, company, location = _split_role_fields(normalized)
                current = ExperienceItem(
                    company=company,
                    job_title=title,
                    location=location,
                    employment_type=_employment_type(normalized),
                    start_date=pending_dates.start if pending_dates else None,
                    end_date=pending_dates.end if pending_dates else None,
                    is_current=bool(pending_dates and pending_dates.is_current),
                    description=[],
                    confidence=0.72,
                )
                pending_dates = None
                continue

            # The line directly beneath a role header — before any bullet has
            # been seen — is that role's company/location line ("U.S. Army,
            # Captain – Fort Hood, TX"), not a new role. It is short, starts
            # capitalized and contains a dash, which is exactly what
            # _looks_like_role_line keys on, so without this every job in a
            # two-line-header resume split into two phantom entries.
            if (
                date_anchored
                and current is not None
                and not current.company
                and not current.description
                and _header_like(normalized)
                and not _ROLE_NOUN.search(normalized)
                and not _NON_COMPANY_LABEL.match(normalized)
                and not normalized.endswith(":")
            ):
                company, location = _company_location_line(normalized)
                if company:
                    current.company = company
                    if location and not current.location:
                        current.location = location
                    if not current.employment_type:
                        current.employment_type = _employment_type(normalized)
                    continue

            if current is not None and not current.company and _looks_like_company_line(normalized):
                company = _extract_company(normalized)
                if company:
                    current.company = company
                    continue

            if current is not None and _looks_like_role_line(normalized):
                if not current.job_title:
                    title, company, location = _split_role_fields(normalized)
                    current.job_title = title
                    current.company = current.company or company
                    current.location = current.location or location
                    continue
                if date_anchored:
                    # Entry boundaries normally come from date ranges. The one
                    # dateless line that may still open a job is a role header
                    # directly beneath a standalone date line — that layout
                    # puts the range above the header instead of on it, so the
                    # range is held in pending_dates and its presence is what
                    # makes this line a header rather than a stray title.
                    # Without that anchor the rule fires on repeated title
                    # lines inside a job and splits it apart.
                    if (
                        pending_dates is not None
                        or _next_line_is_company_with_dates(next_line)
                    ) and _is_strong_role_header(normalized) and (
                        current.company or current.description or current.start_date or current.end_date
                    ):
                        roles.append(current)
                        in_project = False
                        title, company, location = _split_role_fields(normalized)
                        current = ExperienceItem(
                            company=company,
                            job_title=title,
                            location=location,
                            employment_type=_employment_type(normalized),
                            start_date=pending_dates.start if pending_dates else None,
                            end_date=pending_dates.end if pending_dates else None,
                            is_current=bool(pending_dates and pending_dates.is_current),
                            description=[],
                            confidence=0.7,
                        )
                        pending_dates = None
                        continue
                    current.description.append(normalized)
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
        return _inherit_employer(merged)


def _looks_like_role(text: str) -> bool:
    if not text or len(text) > 120:
        return False
    if text.startswith(("-", "•", "*")):
        return False
    return bool(_AT.search(text) or "," in text or " – " in text or " — " in text)


_SENTENCE_END = re.compile(r"[.!?][\"')\]]?\s*$")
_ROLE_NOUN = re.compile(
    r"\b(?:engineer|developer|analyst|manager|architect|trainer|consultant|specialist|"
    r"administrator|designer|director|intern|technician|accountant|nurse|assistant|"
    r"coordinator|supervisor|president|officer|programmer|scientist|lead|associate|"
    r"executive|counselor|therapist|processor|representative|clerk|teacher|recruiter|"
    r"tester|founder|owner|instructor|tutor|auditor|planner|editor|strategist|"
    r"technologist|estimator|inspector|controller|paralegal|pharmacist|attorney)\b",
    re.I,
)


def _looks_like_role_line(text: str) -> bool:
    """A title/company line, as opposed to a prose bullet.

    This deliberately does NOT fire on "contains a comma" alone: ordinary
    bullet prose is full of commas, and treating those as role lines split
    single jobs into dozens of phantom entries across a real corpus. A real
    title/company line is short, starts capitalized, and doesn't read as a
    finished sentence.
    """
    if not text or len(text) > 140:
        return False
    if text.startswith(("-", "•", "*", "●")):
        return False
    if text[:1].islower():
        return False
    words = text.split()
    if len(words) > 14:
        return False
    if _SENTENCE_END.search(text) and len(words) > 8:
        return False
    if _ROLE_NOUN.search(text):
        return True
    if _AT.search(text) or " – " in text or " — " in text:
        return True
    # A comma alone is far too weak on its own, but a *compact* comma line
    # that isn't a finished sentence is the classic "Company, City ST" form.
    return "," in text and len(words) <= 8 and not _SENTENCE_END.search(text)


_PROJECT_ROLE_LABELS = {"role", "designation", "position"}
_PROJECT_TECH_LABELS = {
    "stack",
    "tech stack",
    "technology stack",
    "technologies",
    "technology",
    "tools",
    "environment",
}


def _apply_project_metadata(item: ExperienceItem | None, text: str) -> None:
    """Handle the "Role: … | Stack: …" line under an embedded project header.

    It is the block's sub-text, the counterpart of the "Company | Location"
    line under an ordinary role header. The entry is already named by the
    heading above it, so the line is kept verbatim as the first description
    item rather than overwriting that name, and only the stack is lifted out
    into a structured field.
    """
    if item is None:
        return
    for chunk in re.split(r"\s*\|\s*", text):
        label, remainder = split_label_prefix(chunk)
        if not label or not remainder:
            continue
        if label.lower() in _PROJECT_TECH_LABELS and not item.technologies:
            item.technologies = _techs(chunk)
    item.description.append(text)


def _is_date_anchored(lines: list[str]) -> bool:
    """True when this experience section uses date ranges as its entry
    anchors — i.e. at least two non-bullet lines carry one.

    Nearly every real resume does, and it is the structure a human reads
    first: scan the date column, and each range is one job. Treating dates
    as the anchor lets every other line be absorbed into the job it belongs
    to instead of competing to start a new one, which is where the phantom
    entries came from. Sections with no usable dates keep the older
    shape-based heuristics.
    """
    dated = 0
    for line in lines:
        if _BULLET_RAW.match(line):
            continue
        text = _clean_description_text(line)
        if not text:
            continue
        if parse_date_range(text) or _paren_or_single_date(text):
            dated += 1
            if dated >= 2:
                return True
    return False


_COLUMN_GAP = re.compile(r"\t+|\s{2,}")


def _columns(text: str) -> list[str]:
    """Split a header line on its *layout* columns — tab runs or wide space
    runs — which is how many resumes separate company, location and dates
    ("Sather Insurance Marketeers<tab>Palatine, IL<tab>07/1983 - 01/1990").

    Whitespace is collapsed by `clean_line` before any parsing, so this must
    be read off the raw line; otherwise the only remaining boundary is the
    comma inside "Palatine, IL" and the city gets absorbed into the company.
    """
    parts = [part.strip() for part in _COLUMN_GAP.split(text) if part.strip()]
    return parts if len(parts) >= 2 else []


def _column_role_fields(raw_line: str) -> tuple[str | None, str | None, str | None] | None:
    """(title, company, location) read off a columnar header line, or None
    when the columns are too ambiguous to be better evidence than the text."""
    columns = [column for column in _columns(raw_line) if not parse_date_range(column)]
    if (
        len(columns) == 2
        and _looks_like_location(columns[1])
        # "Senior Engineer<tab>Acme Corp, Austin, TX" has the same shape but
        # the opposite meaning; a role noun in the first column rules out
        # reading it as the company.
        and not _ROLE_NOUN.search(columns[0])
    ):
        return None, _clean(columns[0]), _clean(columns[1])
    if len(columns) == 3 and _looks_like_location(columns[2]):
        return _clean(columns[0]), _clean(columns[1]), _clean(columns[2])
    # A single remaining column is just the title ("IT Manager<tab>Jan 2020 -
    # Dec 2021"); anything wider is unclear. Both are left to the text rules.
    return None


def _header_like(text: str) -> bool:
    """Short, capitalized, not a finished sentence — the shape of a header
    line (title, company/location) rather than prose."""
    if not text or text[:1].islower():
        return False
    words = text.split()
    if not words or len(words) > 14:
        return False
    return not _SENTENCE_END.search(text)


_CORP_SUFFIX = re.compile(
    r"(?i)^(?:l\.?l\.?c|l\.?l\.?p|inc|ltd|limited|plc|p\.?c|corp|corporation|co|company|"
    r"gmbh|pvt|private limited|s\.?a|a\.?g|b\.?v|n\.?v|group|holdings|llc\.)\.?$"
)
_FIELD_SEPARATOR = re.compile(r"\s*[|•]\s*|\s+[–—-]\s+")


def _company_location_line(text: str) -> tuple[str | None, str | None]:
    """Split a company/location line into its two parts.

    Handles the forms that show up on the line under a role header:
    "Company – City, ST", "Company | City", "Company, LLC – City, ST" (the
    comma belongs to the company name), and "Company, Rank/Division – City,
    ST" (the comma introduces a qualifier that is neither company nor
    location).
    """
    company, location = text, None
    separators = list(_FIELD_SEPARATOR.finditer(text))
    if separators:
        last = separators[-1]
        company, location = text[: last.start()].strip(), text[last.end() :].strip()
    if "," in company:
        head, tail = company.rsplit(",", 1)
        tail = tail.strip()
        if _CORP_SUFFIX.match(tail):
            pass  # "In Pursuit Of, LLC" — the suffix is part of the name.
        elif location is None:
            company, location = head.strip(), tail
        elif len(tail.split()) <= 2:
            # A location was already taken from the dash, so this trailing
            # fragment is a rank or division ("U.S. Army, Captain").
            company = head.strip()
    return _clean(company), (_clean(location) if location else None)


_DATE_FRAGMENT = re.compile(
    r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\b\d{4}\b|"
    r"\b(?:present|current|till date|to date)\b"
)
_PRESENT_WORD = re.compile(r"(?i)^(?:present|current|now|ongoing|till date|to date)$")
_OPEN_RANGE = re.compile(r"^(?P<left>[^–—-]{0,24}?)\s*[–—-]\s*(?P<right>[^–—-]{0,24})$")


def _partial_date_line(text: str) -> DateSpan | None:
    """A standalone date line with one unreadable half.

    Some PDFs truncate the year in the text layer — one real resume carries
    "AUGUST 201 - PRESENT" and "20- JUNE 2016" as its two job dates. The
    missing year cannot be recovered and must not be guessed, but the legible
    half still says when the job ended, or that it is ongoing, and that beats
    dropping the line into the previous job's bullets.
    """
    stripped = text.strip()
    if len(stripped.split()) > 6 or not _DATE_FRAGMENT.search(stripped):
        return None
    match = _OPEN_RANGE.match(stripped)
    if not match:
        return None
    left, right = match.group("left").strip(), match.group("right").strip()
    is_current = bool(_PRESENT_WORD.match(right))
    start = parse_date_token(left)
    end = None if is_current else parse_date_token(right)
    if start is None and end is None and not is_current:
        return None
    return DateSpan(start=start, end=end, is_current=is_current, raw=stripped)


def _next_meaningful(lines: list[str], index: int) -> str | None:
    for candidate in lines[index + 1 :]:
        text = _clean_description_text(candidate)
        if text:
            return text
    return None


def _next_line_is_company_with_dates(text: str | None) -> bool:
    """True when the following line carries a company and a date range but no
    job title of its own — which means the title is the line above it.

    "Clinical Therapist" / "Orlando Recovery Ctr - Orlando, FL  August 2020 to
    Present" is one job written across two lines; without this the title line
    is swallowed as a bullet of the previous job.
    """
    if not text:
        return False
    dates = parse_date_range(text)
    if dates is None:
        return False
    base = _clean_description_text(strip_date_range(text))
    if not base or not _header_like(base):
        return False
    title, company, _ = _split_role_fields(base)
    return company is not None and title is None


def _is_strong_role_header(text: str) -> bool:
    """A dateless line that still unambiguously opens a job, because the part
    before its first separator is itself a job title.

    This is what separates "QA AUTOMATION ENGINEER, Alliance Tek Solutions"
    (a role header) from "U.S. Army, Captain - Fort Hood, TX" (the company
    line beneath one). Both are short, capitalized and comma-separated; only
    the first *leads* with a role.
    """
    if not _header_like(text):
        return False
    lead = re.split(r"\s*[,|]\s*|\s+[-–—]\s+", text, maxsplit=1)[0].strip()
    if not lead or len(lead.split()) > 6:
        return False
    return bool(_ROLE_NOUN.search(lead))


def _looks_like_company_line(text: str) -> bool:
    """Matching was substring-based and unbounded, so "includes" supplied the
    "inc" and any paragraph of prose qualified as a company name — whole
    project descriptions ended up in the company field. Require a real word
    match on a line that is shaped like a header."""
    if not _header_like(text):
        return False
    if _COMPANY_MARKER.search(text):
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


def _is_bare_place(text: str) -> bool:
    """True for "Miami, Florida" / "Billerica, MA" — a header line that is
    only a place, with no employer on it. Reporting the city as the company
    would be inventing an employer the resume never named."""
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2 or not parts[0] or not is_us_state(parts[1]):
        return False
    if len(parts[0].split()) > 3:
        return False
    return not _COMPANY_MARKER.search(parts[0])


_COMPANY_MARKER = re.compile(
    r"(?i)\b(?:inc|llc|ltd|corp|corporation|company|co|group|holdings|technologies|"
    r"solutions|systems|services|consulting|labs|university|college|bank|plc|gmbh|pvt)\b"
)


def _split_role_fields(text: str) -> tuple[str | None, str | None, str | None]:
    separators = list(_FIELD_SEPARATOR.finditer(text))
    if separators:
        head = text[: separators[-1].start()].strip()
        tail = text[separators[-1].end() :].strip()
        # An explicit separator with a place on its right draws the boundary
        # far more reliably than the commas inside either half do: without
        # this, "SEI - Oaks, Pennsylvania" splits at the comma and reports
        # the employer as "SEI - Oaks".
        if head and tail and _looks_like_location(tail) and not _ROLE_NOUN.search(tail):
            if _ROLE_NOUN.search(head):
                return _clean(head), None, _clean(tail)
            company, location = _company_location_line(text)
            return None, company, location
    if _is_bare_place(text):
        return None, None, _clean(text)
    suffix = _TITLE_SUFFIX.search(text)
    if suffix and ("," in text or _AT.search(text)):
        title = _clean(suffix.group("title"))
        rest = text[: suffix.start()].strip(" ,-|")
        if "," in rest:
            left, right = rest.split(",", 1)
            # Only split off a location when the tail actually reads as one;
            # "PMO Custom Extract, Retrieval Implementations" is one company
            # name and must not have half of it reported as a location.
            if _looks_like_location(right):
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


_LEVEL_SUFFIX = re.compile(r"^(?:[IVX]{1,4}|[0-9]+)$")


def _split_title_company(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    candidates = [part.strip() for part in re.split(r"\n+|\s*\|\s*|\s*(?:—|–|-)\s*", text) if part.strip()]
    if len(candidates) >= 2:
        title = candidates[0]
        company = None
        consumed_as_level = False
        for candidate in candidates[1:]:
            if _LEVEL_SUFFIX.match(candidate):
                # "Software Engineer - I" / "Developer - II" — a seniority
                # level suffix, not a company; keep it attached to the title.
                title = f"{title} - {candidate}"
                consumed_as_level = True
                continue
            if _looks_like_role(candidate) or re.fullmatch(
                r"\d{4}(?:\s*[–—-]\s*(?:Present|Current|\d{4}))?", candidate
            ):
                continue
            company = candidate
            break
        if company:
            return _clean(title), _clean(company)
        if consumed_as_level:
            return _clean(title), None
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
    """A comma is not evidence of a location — resume text is full of them,
    and treating "PMO Custom, Extract, Retrieval Implementations" as a
    place put half a job title in the location field. Require the tail to
    actually name a state or country."""
    value = text.strip()
    if not value:
        return False
    if is_state_or_country(value):
        return True
    tail = value.rsplit(",", 1)[-1]
    if is_state_or_country(tail):
        return True
    return bool(re.search(r"\b(usa|united states|india|uk|canada|remote)\b", value, re.I))


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


def _start_year(value: str | None) -> int | None:
    match = re.match(r"^(\d{4})", value or "")
    return int(match.group(1)) if match else None


def _inherit_employer(roles: list[ExperienceItem]) -> list[ExperienceItem]:
    """Give promotion-history sub-roles the employer they sit under.

    A long tenure is often written as one employer header ("SEI, Oaks,
    Pennsylvania  1998 - 2013") followed by the internal roles held there,
    each with its own dates but no company repeated. Read in isolation those
    roles look companyless; read in order — the way a person reads the page —
    they plainly belong to the employer whose span encloses them.

    A role whose span falls inside the current employer's is treated as a
    sub-role even when it did parse a company of its own, so a garbled line
    in the middle of a tenure cannot hijack the employer for the roles below
    it.
    """
    employer: tuple[str, str | None, int, int | None] | None = None
    for role in roles:
        start = _start_year(role.start_date)
        end = _start_year(role.end_date)
        enclosed = (
            employer is not None
            and start is not None
            and employer[2] <= start
            and (employer[3] is None or (end is not None and end <= employer[3]))
        )
        if role.company:
            if not enclosed and start is not None:
                employer = (role.company, role.location, start, None if role.is_current else end)
            continue
        if enclosed and employer is not None:
            role.company = employer[0]
            if not role.location:
                role.location = employer[1]
    return roles


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
