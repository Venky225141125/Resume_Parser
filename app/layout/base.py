from abc import ABC, abstractmethod

from app.schemas.document import Document


class LayoutAnalyzer(ABC):
    """Reconstruct logical reading order from coordinates."""

    @abstractmethod
    def analyze(self, document: Document) -> Document:
        raise NotImplementedError
