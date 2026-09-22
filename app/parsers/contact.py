from __future__ import annotations

import re
from urllib.parse import urlparse

import phonenumbers

from app.normalization.location import POSTAL_PATTERN, LocationNormalizer
from app.parsers.base import FieldParser
from app.parsers.support import is_known_section_heading, preamble_lines
from app.schemas.candidate import ContactInfo, LinkInfo, LocationInfo, NameInfo
from app.schemas.document import Document
from app.sections.base import DetectedSection

_EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
_URL = re.compile(r"https?://[^\s)>\]]+", re.I)
_PHONE_FALLBACK = re.compile(r"(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{3}\)?[\s.\-]?)?\d{3}[\s.\-]?\d{4}")

_SECTION_WORDS = {
    "experience",
    "education",
    "skills",
    "summary",
    "objective",
    "projects",
    "certifications",
}

_ROLE_WORDS = {
    "developer",
    "engineer",
    "manager",
    "analyst",
    "architect",
    "consultant",
    "trainer",
    "lead",
    "specialist",
    "assistant",
    "associate",
    "intern",
    "executive",
    "director",
    "head",
    "principal",
}

_LINK_HOSTS = {
    "linkedin.com": "linkedin",
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "stackoverflow.com": "stackoverflow",
}


class ContactParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> tuple[NameInfo, ContactInfo, LocationInfo, list[LinkInfo]]:
        blob = _normalize_contact_text(document.plain_text())
        emails = _prefer_emails(_unique(_EMAIL.findall(blob)))
        phones = _extract_phones(blob)
        links = _extract_links(blob)
        header_lines = preamble_lines(sections, document)
        if not header_lines:
            # Only fall back to the unrestricted first blocks when section
            # detection found no header section at all — otherwise this
            # reaches straight past a short header/summary into the
            # Experience section and picks up a job's "Company, City, ST"
            # as if it were the candidate's own location.
            header_lines = [block.text.strip() for block in document.blocks[:12] if block.text.strip()]
        combined_lines = header_lines
        name = _extract_name(combined_lines)
        location = _extract_location(combined_lines, exclude=name.full)
        contact = ContactInfo(
            email=emails[0] if emails else None,
            phone=phones[0] if phones else None,
            alternate_phone=phones[1] if len(phones) > 1 else None,
        )
        return name, contact, location, links


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


def _normalize_contact_text(text: str) -> str:
    return re.sub(
        r"@([A-Za-z0-9.\-]+)\.\s+(com|net|org|edu|in)\b",
        r"@\1.\2",
        text,
        flags=re.I,
    )


def _prefer_emails(emails: list[str]) -> list[str]:
    real = [
        email
        for email in emails
        if "proxy.jobs.net" not in email.lower() and "~" not in email
    ]
    rest = [email for email in emails if email not in real]
    return real + rest


def _extract_phones(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    seen_spans: set[tuple[int, int]] = set()
    for region in ("US", "IN", "GB", None):
        try:
            matches = phonenumbers.PhoneNumberMatcher(text, region)
        except Exception:
            continue
        for match in matches:
            # The same digits match under several regions ("631-806-6076"
            # is +1... as US and +91... as IN), producing what looks like a
            # second, alternate phone number. Whichever region claims a span
            # first wins; later regions must not re-report the same span.
            span = (match.start, match.start + len(match.raw_string))
            if span in seen_spans:
                continue
            formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
            if formatted in seen:
                seen_spans.add(span)
                continue
            seen.add(formatted)
            seen_spans.add(span)
            found.append(formatted)
    if found:
        return found
    for raw in _PHONE_FALLBACK.findall(text):
        compact = re.sub(r"[^\d+]", "", raw)
        if len(re.sub(r"\D", "", compact)) < 10:
            continue
        if compact not in seen:
            seen.add(compact)
            found.append(raw.strip())
    return found


def _extract_links(text: str) -> list[LinkInfo]:
    links: list[LinkInfo] = []
    seen: set[str] = set()
    for raw in _URL.findall(text):
        cleaned = raw.rstrip(".,);")
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        host = parsed.netloc.lower().removeprefix("www.")
        link_type = "website"
        for needle, label in _LINK_HOSTS.items():
            if host == needle or host.endswith("." + needle):
                link_type = label
                break
        links.append(LinkInfo(type=link_type, url=cleaned, confidence=0.95))
    lowered = text.lower()
    if "linkedin.com" in lowered and not any(item.type == "linkedin" for item in links):
        match = re.search(r"(linkedin\.com/in/[A-Za-z0-9_\-/%]+)", text, re.I)
        if match:
            url = "https://" + match.group(1).rstrip(".,)")
            links.append(LinkInfo(type="linkedin", url=url, confidence=0.9))
    if "github.com" in lowered and not any(item.type == "github" for item in links):
        match = re.search(r"(github\.com/[A-Za-z0-9_\-]+)", text, re.I)
        if match:
            url = "https://" + match.group(1).rstrip(".,)")
            links.append(LinkInfo(type="github", url=url, confidence=0.9))
    return links


_HEADER_SEPARATORS = re.compile(r"[|•·‣⁃●]")
_INLINE_LABEL = re.compile(r"(?i)\b(?:full name|location|address|email|e-mail|phone|mobile|tel)\s*:")


def _header_segments(text: str) -> list[str]:
    """Split a header/contact-bar line into name/location/contact segments.

    Two distinct gluing patterns show up in the wild: explicit separators
    ("Name | Phone | Email", "Name . City, State . Phone"), and a two-column
    header row where a field *label* runs straight into the next field with
    just a space ("EDUBILLI VENKATESH Location: Anavaram, Vizianagaram,
    Andhra Pradesh - INDIA" — name and "Location:" on the same visual PDF
    row, extracted as one line). Both must be split or the combined line is
    too long / contains contact info and gets discarded as a name/location
    candidate wholesale.
    """
    parts = [text]
    if _HEADER_SEPARATORS.search(text):
        split = [part.strip() for part in _HEADER_SEPARATORS.split(text) if part.strip()]
        if len(split) > 1:
            parts = split
    expanded: list[str] = []
    for part in parts:
        match = _INLINE_LABEL.search(part)
        if match and match.start() > 0:
            expanded.append(part[: match.start()].strip(" ,-"))
            expanded.append(part[match.start() :].strip())
        else:
            expanded.append(part)
    return expanded


def _strip_inline_label(segment: str) -> str:
    match = _INLINE_LABEL.match(segment)
    if not match:
        return segment
    return segment[match.end() :].strip(" :")


def _strip_contact_noise(text: str) -> str:
    """Remove email/phone/url substrings (and separator glyphs) from a line
    that glues the name/location to contact details with no separator at
    all, e.g. "Jane Doe jane.doe@example.com +1 415 555 0100"."""
    cleaned = _EMAIL.sub(" ", text)
    cleaned = _URL.sub(" ", cleaned)
    cleaned = _PHONE_FALLBACK.sub(" ", cleaned)
    cleaned = _HEADER_SEPARATORS.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ,")


def _extract_name(lines: list[str]) -> NameInfo:
    for index, line in enumerate(lines[:6]):
        text = line.strip()
        if not text:
            continue
        allow_comma_prefix = index == 0
        for segment in _header_segments(text):
            candidate = _name_from_segment(segment, allow_comma_prefix)
            if candidate:
                return candidate
        stripped = _strip_contact_noise(text)
        if stripped and stripped != text:
            candidate = _name_from_segment(stripped, allow_comma_prefix)
            if candidate:
                return candidate
    return NameInfo()


def _name_from_segment(text: str, allow_comma_prefix: bool = False) -> NameInfo | None:
    candidate = _name_from_words(text)
    if candidate:
        return candidate
    if allow_comma_prefix and "," in text:
        # "Thelma Serrano, MS.,RMHCI, IMH20981" / "Helen B. Couch, CPA, CCM"
        # — a name followed by post-nominal credentials is common enough to
        # special-case, but only on the very first line: a "City, ST" line
        # later in the header would otherwise look exactly as name-shaped.
        prefix = text.split(",", 1)[0].strip()
        return _name_from_words(prefix)
    return None


def _name_from_words(text: str) -> NameInfo | None:
    if not text or _EMAIL.search(text) or _URL.search(text) or _PHONE_FALLBACK.search(text):
        return None
    if is_known_section_heading(text):
        return None
    if _looks_like_job_title(text):
        return None
    words = [part for part in re.split(r"\s+", text) if part]
    if not 2 <= len(words) <= 7:
        return None
    if any(ch.isdigit() for ch in text):
        return None
    if not all(re.match(r"^[A-Za-z][A-Za-z.'\-]*$", word) or re.match(r"^[A-Z][A-Z.'\-]*$", word) for word in words):
        return None
    first = words[0]
    last = words[-1]
    middle = " ".join(words[1:-1]) if len(words) > 2 else None
    return NameInfo(
        full=" ".join(words),
        first=first,
        middle=middle,
        last=last,
        confidence=0.8,
    )


def _looks_like_job_title(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return False
    words = re.findall(r"[A-Za-z]+", lowered)
    if not words:
        return False
    if len(words) > 8:
        return False
    score = sum(1 for word in words if word in _ROLE_WORDS)
    return score > 0 or lowered.startswith("java ") or lowered.startswith("python ")


_STATE_COMMA = re.compile(r",\s*[A-Z]{2}\b")


def _extract_location(lines: list[str], exclude: str | None = None) -> LocationInfo:
    normalizer = LocationNormalizer()
    best: tuple[int, str] | None = None

    def consider(candidate: str) -> None:
        nonlocal best
        score = _location_score(candidate)
        if best is None or score > best[0]:
            best = (score, candidate)

    for line in lines:
        for segment in _header_segments(line):
            if _looks_like_location_segment(segment):
                consider(_strip_inline_label(segment))
        stripped = _strip_contact_noise(line)
        if exclude:
            stripped = re.sub(re.escape(exclude), " ", stripped, flags=re.I)
            stripped = re.sub(r"\s+", " ", stripped).strip(" ,")
        if stripped and stripped != line.strip() and _looks_like_location_segment(stripped):
            consider(stripped)
    if best is None:
        return LocationInfo()
    return normalizer.normalize(best[1])


def _location_score(segment: str) -> int:
    """Prefer a proper "City, ST ZIP" line over a plain street address or an
    unrelated "Company, City, ST" line pulled from elsewhere in the header —
    both of which also contain a comma."""
    score = 1  # already passed _looks_like_location_segment
    if POSTAL_PATTERN.search(segment):
        score += 2
    if _STATE_COMMA.search(segment):
        score += 2
    return score


def _looks_like_location_segment(segment: str) -> bool:
    if not segment or len(segment) >= 80:
        return False
    if _EMAIL.search(segment) or "http" in segment.lower():
        return False
    if any(word in segment.lower() for word in _SECTION_WORDS):
        return False
    return bool(POSTAL_PATTERN.search(segment) or "," in segment)
