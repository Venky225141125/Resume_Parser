from app.parsers.base import FieldParser
from app.parsers.support import combined_text
from app.schemas.document import Document
from app.sections.base import DetectedSection


class SummaryParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> str | None:
        text = combined_text(sections, "summary")
        cleaned = text.strip()
        return cleaned or None
