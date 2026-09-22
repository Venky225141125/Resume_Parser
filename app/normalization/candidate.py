from __future__ import annotations

from app.normalization.base import Normalizer
from app.normalization.degree import DegreeNormalizer
from app.normalization.skills import SkillNormalizer
from app.schemas.candidate import CandidateDocument


class CandidateNormalizer(Normalizer):
    """Idempotent normalization pass over an assembled CandidateDocument.

    Parsers already canonicalize most values inline as part of extraction
    (dictionary/gazetteer lookups need the taxonomy at extraction time, not
    after). This stage re-runs the same canonicalizers so any item that
    arrives without a normalized value already set (e.g. a future LLM-
    extracted field) still gets canonicalized before validation/confidence.
    """

    def __init__(self) -> None:
        self._skills = SkillNormalizer()
        self._degrees = DegreeNormalizer()

    def normalize(self, document: CandidateDocument) -> CandidateDocument:
        document.skills = self._skills.normalize(document.skills)
        for item in document.education:
            if item.degree and not item.degree_normalized:
                item.degree_normalized = self._degrees.normalize(item.degree)
        return document
