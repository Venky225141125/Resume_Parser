from app.normalization.base import Normalizer
from app.normalization.candidate import CandidateNormalizer
from app.normalization.degree import DegreeNormalizer
from app.normalization.location import LocationNormalizer
from app.normalization.skills import SkillNormalizer

__all__ = [
    "CandidateNormalizer",
    "DegreeNormalizer",
    "LocationNormalizer",
    "Normalizer",
    "SkillNormalizer",
]
