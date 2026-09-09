from app.core.exceptions import UnsupportedMediaError
from app.extraction.base import DocumentExtractor
from app.extraction.docx.extractor import DocxExtractor
from app.extraction.pdf.extractor import PdfExtractor
from app.extraction.txt import TxtExtractor


class ExtractorRegistry:
    def __init__(self, extractors: list[DocumentExtractor] | None = None) -> None:
        self._extractors = extractors or [
            PdfExtractor(),
            DocxExtractor(),
            TxtExtractor(),
        ]

    def get(self, file_type: str) -> DocumentExtractor:
        for extractor in self._extractors:
            if extractor.supports(file_type):
                return extractor
        raise UnsupportedMediaError(f"No extractor registered for type '{file_type}'.")
