"""Structure a raw "City, State, Country" line into LocationInfo and
canonicalize the country name. Extraction (app.parsers.contact) still owns
deciding *which* line is the location line."""

from __future__ import annotations

import re

from app.normalization.base import Normalizer
from app.schemas.candidate import LocationInfo

POSTAL_PATTERN = re.compile(r"\b(\d{6}|\d{5}(?:-\d{4})?)\b")

US_STATE_ABBREVIATIONS = frozenset(
    """AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS
    MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI
    WY DC PR VI GU AS MP""".split()
)

US_STATE_NAMES = frozenset(
    name.lower()
    for name in """Alabama Alaska Arizona Arkansas California Colorado Connecticut
    Delaware Florida Georgia Hawaii Idaho Illinois Indiana Iowa Kansas Kentucky
    Louisiana Maine Maryland Massachusetts Michigan Minnesota Mississippi Missouri
    Montana Nebraska Nevada Ohio Oklahoma Oregon Pennsylvania Tennessee Texas Utah
    Vermont Virginia Washington Wisconsin Wyoming""".split()
)

# Two-word state names, kept separate so the single-token split above stays simple.
US_STATE_NAMES = US_STATE_NAMES | frozenset(
    {
        "new hampshire",
        "new jersey",
        "new mexico",
        "new york",
        "north carolina",
        "north dakota",
        "rhode island",
        "south carolina",
        "south dakota",
        "west virginia",
        "district of columbia",
        "puerto rico",
    }
)

_COMMON_COUNTRIES = frozenset(
    {
        "united states", "usa", "u.s.a", "u.s", "us", "india", "united kingdom",
        "uk", "england", "scotland", "wales", "ireland", "canada", "australia",
        "new zealand", "germany", "france", "spain", "italy", "netherlands",
        "singapore", "japan", "china", "south africa", "mexico", "brazil",
        "philippines", "malaysia", "uae", "united arab emirates", "remote",
    }
)


def is_us_state(value: str) -> bool:
    """True only for a US state name or postal abbreviation.

    Narrower than `is_state_or_country` on purpose: "City, ST" is an
    unambiguous US address idiom, whereas "Word, Country" is just as often
    "Company, Country" ("Contoso, India") and cannot be read as a place on
    punctuation alone.
    """
    token = value.strip().strip(".,")
    if not token:
        return False
    if len(token) == 2 and token.isalpha() and token.upper() in US_STATE_ABBREVIATIONS:
        return True
    return re.sub(r"\s+", " ", token).lower() in US_STATE_NAMES


def is_state_or_country(value: str) -> bool:
    """True when `value` names a US state (by name or postal abbreviation) or
    a country — the reliable right-hand half of a "City, State" pair.

    Used to tell a real location apart from any other comma-separated tail,
    which is otherwise indistinguishable by punctuation alone.
    """
    token = value.strip().strip(".,")
    if not token:
        return False
    if token.upper() in US_STATE_ABBREVIATIONS and token.isalpha() and len(token) == 2:
        return True
    lowered = re.sub(r"\s+", " ", token).lower()
    return lowered in US_STATE_NAMES or lowered in _COMMON_COUNTRIES
_EMBEDDED_COUNTRY = re.compile(
    r"(?i)\b(united states|usa|india|united kingdom|uk|canada)\b",
)
_COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "india": "India",
    "canada": "Canada",
}


class LocationNormalizer(Normalizer):
    def normalize(self, raw_line: str) -> LocationInfo:
        parts = [part.strip() for part in raw_line.split(",") if part.strip()]
        city = parts[0] if parts else None
        state = parts[1] if len(parts) > 1 else None
        country = parts[2] if len(parts) > 2 else None
        postal_match = POSTAL_PATTERN.search(raw_line)
        postal = postal_match.group(1) if postal_match else None
        if state:
            state = _strip_postal(state)
            country_match = _EMBEDDED_COUNTRY.search(state)
            if country_match and country is None:
                country = country_match.group(1)
                state = state[: country_match.start()].strip(" ,")
        if country:
            country = _strip_postal(country)
            country_match = _EMBEDDED_COUNTRY.search(country)
            if country_match:
                # A 4-level address ("City, District, State - Country") only
                # has 3 comma parts, so the country field can still contain
                # "State - Country" glued together. The chunk before the
                # matched country name is a better state value than whatever
                # the raw 2nd comma segment held (often a district/region).
                prefix = country[: country_match.start()].strip(" -,")
                if prefix:
                    state = prefix
                country = country_match.group(1)
            country = _canonicalize_country(country)
        return LocationInfo(raw=raw_line, city=city, state=state, country=country, postal_code=postal)


def _strip_postal(value: str) -> str:
    """Drop a bare or parenthesized postal/PIN code trailing a state or
    country segment ("CA 94105", "India 500032", "TX (75001)")."""
    cleaned = re.sub(r"\(\s*\d{5,6}(?:-\d{4})?\s*\)", "", value)
    cleaned = POSTAL_PATTERN.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ,-")


def _canonicalize_country(value: str) -> str:
    return _COUNTRY_ALIASES.get(value.strip().lower(), value.strip())
