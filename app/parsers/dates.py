from __future__ import annotations

import re
from dataclasses import dataclass

_MONTHS = {
    "january": "01",
    "jan": "01",
    "february": "02",
    "feb": "02",
    "march": "03",
    "mar": "03",
    "april": "04",
    "apr": "04",
    "may": "05",
    "june": "06",
    "jun": "06",
    "july": "07",
    "jul": "07",
    "august": "08",
    "aug": "08",
    "september": "09",
    "sept": "09",
    "sep": "09",
    "october": "10",
    "oct": "10",
    "november": "11",
    "nov": "11",
    "december": "12",
    "dec": "12",
}

_PRESENT = re.compile(r"^(present|current|now|ongoing)$", re.I)

_MONTH_NAME = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

# Order matters: the full M/D/Y form must be tried before M/Y, or "03/02/2017"
# matches only its bare year and the surrounding range fails to parse.
_DATE_TOKEN = (
    # "Feb'19", "Apr' 17" — apostrophe-abbreviated years, straight or curly.
    rf"{_MONTH_NAME}\.?\s*['‘’]\s*\d{{2}}\b"
    rf"|{_MONTH_NAME}\.?\s*\d{{1,2}},?\s*\d{{4}}"
    rf"|{_MONTH_NAME}\.?\s*\d{{4}}"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{1,2}/\d{4}"
    r"|\d{4}-\d{2}"
    r"|\d{4}"
)

_RANGE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*(?:[-–—]+|\bto\b)\s*"
    rf"(?P<end>present|current|now|ongoing|{_DATE_TOKEN})",
    re.I,
)


@dataclass(slots=True)
class DateSpan:
    start: str | None
    end: str | None
    is_current: bool
    raw: str | None


def parse_date_token(token: str) -> str | None:
    text = token.strip().rstrip(".")
    if not text:
        return None
    if _PRESENT.match(text):
        return None
    month_year = re.match(
        r"^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\.?\s*(\d{4})$",
        text,
        re.I,
    )
    if month_year:
        month = _MONTHS[month_year.group(1).lower()[:3] if month_year.group(1).lower()[:3] in _MONTHS else month_year.group(1).lower()]
        # sept -> sep handled: use full key
        key = month_year.group(1).lower().rstrip(".")
        if key not in _MONTHS:
            key = key[:3]
        month = _MONTHS.get(key) or _MONTHS.get(key[:3])
        if not month:
            return None
        return f"{month_year.group(2)}-{month}"
    short_year = re.match(
        r"^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\.?\s*['‘’]\s*(\d{2})$",
        text,
        re.I,
    )
    if short_year:
        key = short_year.group(1).lower().rstrip(".")
        month = _MONTHS.get(key) or _MONTHS.get(key[:3])
        if not month:
            return None
        year = int(short_year.group(2))
        return f"{2000 + year if year <= 29 else 1900 + year}-{month}"
    day_month_year = re.match(
        r"^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\.?\s*\d{1,2},?\s*(\d{4})$",
        text,
        re.I,
    )
    if day_month_year:
        key = day_month_year.group(1).lower().rstrip(".")
        month = _MONTHS.get(key) or _MONTHS.get(key[:3])
        if month:
            return f"{day_month_year.group(2)}-{month}"
        return None
    numeric = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", text)
    if numeric:
        # US convention (month first) — the dominant form in this corpus.
        month_n = int(numeric.group(1))
        if not 1 <= month_n <= 12:
            return None
        year = numeric.group(3)
        if len(year) == 2:
            # Two-digit years in resumes are work history, never the future.
            year = f"20{year}" if int(year) <= 29 else f"19{year}"
        return f"{year}-{month_n:02d}"
    slash = re.match(r"^(\d{1,2})/(\d{4})$", text)
    if slash:
        month_n = int(slash.group(1))
        if 1 <= month_n <= 12:
            return f"{slash.group(2)}-{month_n:02d}"
        return None
    iso_month = re.match(r"^(\d{4})-(\d{2})$", text)
    if iso_month:
        month_n = int(iso_month.group(2))
        if 1 <= month_n <= 12:
            return f"{iso_month.group(1)}-{iso_month.group(2)}"
        return None
    year = re.match(r"^(\d{4})$", text)
    if year:
        return year.group(1)
    return None


def parse_date_range(text: str) -> DateSpan | None:
    match = _RANGE.search(text)
    if not match:
        return None
    start_raw = match.group("start")
    end_raw = match.group("end")
    is_current = bool(_PRESENT.match(end_raw.strip()))
    start = parse_date_token(start_raw)
    end = None if is_current else parse_date_token(end_raw)
    return DateSpan(start=start, end=end, is_current=is_current, raw=match.group(0))


def strip_date_range(text: str) -> str:
    return _RANGE.sub("", text).strip(" -,–—|")
