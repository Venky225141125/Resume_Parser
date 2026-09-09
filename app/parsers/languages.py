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


class LanguageParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[LanguageItem]:
        items: list[LanguageItem] = []
        for line in section_lines(sections, "languages"):
            for chunk in re.split(r"[,;/|]+", line):
                text = chunk.strip()
                if not text:
                    continue
                proficiency = None
                language = text
                for key, label in _PROFICIENCY.items():
                    if key in text.lower():
                        proficiency = label
                        language = re.sub(re.escape(key), "", text, flags=re.I).strip(" -:()")
                        break
                if language:
                    items.append(
                        LanguageItem(language=language, proficiency=proficiency, confidence=0.8)
                    )
        return items
