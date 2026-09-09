from abc import ABC, abstractmethod
from typing import Any

from app.schemas.document import Document
from app.sections.base import DetectedSection


class FieldParser(ABC):
    """Parses one candidate facet from layout-aware sections."""

    @abstractmethod
    def parse(self, document: Document, sections: list[DetectedSection]) -> Any:
        raise NotImplementedError
