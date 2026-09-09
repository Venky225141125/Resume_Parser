from abc import ABC, abstractmethod

from app.schemas.candidate import CandidateDocument


class ConfidenceScorer(ABC):
    """Explainable scores derived from extraction source, not random values."""

    @abstractmethod
    def score(self, document: CandidateDocument) -> tuple[float, bool]:
        """Return (overall_confidence, needs_review)."""
        raise NotImplementedError
