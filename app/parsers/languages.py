from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.support import section_lines
from app.schemas.candidate import LanguageItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_PROFICIENCY = {
    "native": "Native",
    "mother tongue": "Native",
    "fluent": "Fluent",
    "professional": "Professional",
    "full professional": "Professional",
    "intermediate": "Intermediate",
    "beginner": "Beginner",
    "basic": "Basic",
    "conversational": "Conversational",
}

# Spoken languages only. Programming "Languages:" lists are skills.
_SPOKEN = {
    "english",
    "spanish",
    "french",
    "german",
    "hindi",
    "tamil",
    "telugu",
    "kannada",
    "malayalam",
    "marathi",
    "bengali",
    "gujarati",
    "punjabi",
    "urdu",
    "arabic",
    "chinese",
    "mandarin",
    "cantonese",
    "japanese",
    "korean",
    "portuguese",
    "italian",
    "russian",
    "dutch",
    "swedish",
    "norwegian",
    "danish",
    "finnish",
    "polish",
    "turkish",
    "vietnamese",
    "thai",
    "indonesian",
    "malay",
    "tagalog",
    "filipino",
    "hebrew",
    "persian",
    "farsi",
    "greek",
    "czech",
    "romanian",
    "hungarian",
    "ukrainian",
}


class LanguageParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[LanguageItem]:
        items: list[LanguageItem] = []
        seen: set[str] = set()
        for line in section_lines(sections, "languages"):
            if _looks_like_skill_or_prose(line):
                continue
            for chunk in re.split(r"[,;/|]+", line):
                text = chunk.strip(" -•●*")
                if not text:
                    continue
                proficiency = None
                language = text
                for key, label in _PROFICIENCY.items():
                    if key in text.lower():
                        proficiency = label
                        language = re.sub(re.escape(key), "", text, flags=re.I).strip(" -:()")
                        break
                name = _spoken_name(language)
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                items.append(LanguageItem(language=name, proficiency=proficiency, confidence=0.8))
        return items


def _spoken_name(text: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or len(cleaned.split()) > 3:
        return None
    key = cleaned.lower()
    if key in _SPOKEN:
        return cleaned.title() if cleaned.islower() or cleaned.isupper() else cleaned
    # "English (Fluent)" already stripped proficiency
    first = key.split()[0]
    if first in _SPOKEN:
        return first.title()
    return None


def _looks_like_skill_or_prose(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(("●", "•", "-", "*")):
        return True
    if len(stripped) > 80:
        return True
    lowered = stripped.lower()
    return any(
        token in lowered
        for token in ("java", "spring", "sql", "developer", "experience", "environment:")
    )
