from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas.document import Block, Document


@dataclass(slots=True)
class DetectedSection:
    canonical: str
    title_raw: str | None
    confidence: float
    blocks: list[Block] = field(default_factory=list)


class SectionDetector(ABC):
    @abstractmethod
    def detect(self, document: Document) -> list[DetectedSection]:
        raise NotImplementedError
