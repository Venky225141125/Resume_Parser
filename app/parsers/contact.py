from __future__ import annotations

import re
from urllib.parse import urlparse

import phonenumbers

from app.parsers.base import FieldParser
from app.parsers.support import preamble_lines
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
        blob = document.plain_text()
        emails = _unique(_EMAIL.findall(blob))
        phones = _extract_phones(blob)
        links = _extract_links(blob)
        preamble = [block.text.strip() for block in document.blocks[:12] if block.text.strip()]
        header_lines = preamble_lines(sections, document)
        combined_lines = preamble + header_lines
        name = _extract_name(combined_lines)
        location = _extract_location(combined_lines)
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


def _extract_phones(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for region in ("US", "IN", "GB", None):
        try:
            matches = phonenumbers.PhoneNumberMatcher(text, region)
        except Exception:
            continue
        for match in matches:
            formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
            if formatted in seen:
                continue
            seen.add(formatted)
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


def _extract_name(lines: list[str]) -> NameInfo:
    for line in lines[:6]:
        text = line.strip()
        if not text or _EMAIL.search(text) or _URL.search(text) or _PHONE_FALLBACK.search(text):
            continue
        if text.lower() in _SECTION_WORDS:
            continue
        if _looks_like_job_title(text):
            continue
        words = [part for part in re.split(r"\s+", text) if part]
        if not 2 <= len(words) <= 7:
            continue
        if any(ch.isdigit() for ch in text):
            continue
        if not all(re.match(r"^[A-Za-z][A-Za-z.'\-]*$", word) or re.match(r"^[A-Z][A-Z.'\-]*$", word) for word in words):
            continue
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
    return NameInfo()


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


def _extract_location(lines: list[str]) -> LocationInfo:
    for line in lines:
        if _EMAIL.search(line) or "http" in line.lower():
            continue
        if re.search(r"\d{5}(?:-\d{4})?", line) or "," in line:
            if len(line) < 80 and not any(word in line.lower() for word in _SECTION_WORDS):
                parts = [part.strip() for part in line.split(",") if part.strip()]
                city = parts[0] if parts else None
                state = parts[1] if len(parts) > 1 else None
                country = parts[2] if len(parts) > 2 else None
                postal = None
                postal_match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", line)
                if postal_match:
                    postal = postal_match.group(1)
                return LocationInfo(
                    raw=line,
                    city=city,
                    state=state,
                    country=country,
                    postal_code=postal,
                )
    return LocationInfo()
