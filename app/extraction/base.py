from abc import ABC, abstractmethod

from app.schemas.document import Document


class DocumentExtractor(ABC):
    """Format-specific extractors return the intermediate document only."""

    @abstractmethod
    def supports(self, file_type: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract(self, data: bytes, filename: str, content_type: str) -> Document:
        raise NotImplementedError
