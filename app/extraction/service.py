import logging

from app.core.config import Settings, get_settings
from app.core.logging import log_event
from app.extraction.ingest import ingest
from app.extraction.registry import ExtractorRegistry
from app.schemas.document import Document

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(
        self,
        registry: ExtractorRegistry | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._registry = registry or ExtractorRegistry()
        self._settings = settings or get_settings()

    def extract(self, data: bytes, filename: str, content_type: str | None = None) -> Document:
        detected = ingest(data, filename, content_type, settings=self._settings)
        extractor = self._registry.get(detected.file_type.value)
        document = extractor.extract(data, filename, detected.content_type)
        document.metadata.extension_mismatch = detected.extension_mismatch
        document.metadata.file_type = detected.file_type.value
        document.metadata.content_type = detected.content_type
        document.metadata.filename = filename
        log_event(
            logger,
            "document_extracted",
            file_type=detected.file_type.value,
            size_bytes=len(data),
            page_count=document.metadata.page_count,
            char_count=document.metadata.char_count,
            extractor=document.metadata.extractor,
            needs_ocr=document.metadata.needs_ocr,
            extension_mismatch=detected.extension_mismatch,
        )
        return document
