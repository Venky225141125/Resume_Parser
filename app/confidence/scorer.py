from app.confidence.base import ConfidenceScorer
from app.schemas.candidate import CandidateDocument


class SourceConfidenceScorer(ConfidenceScorer):
    def score(self, document: CandidateDocument) -> tuple[float, bool]:
        parts: list[tuple[float, float]] = []
        name_c = document.candidate.name.confidence if document.candidate.name.full else 0.0
        parts.append((0.15, name_c or 0.0))
        email_c = 0.97 if document.candidate.contact.email else 0.0
        parts.append((0.25, email_c))
        phone_c = 0.9 if document.candidate.contact.phone else 0.0
        parts.append((0.10, phone_c))
        if document.experience:
            exp_c = sum(item.confidence or 0.6 for item in document.experience) / len(document.experience)
        else:
            exp_c = 0.0
        parts.append((0.25, exp_c))
        edu_c = 0.8 if document.education else 0.0
        parts.append((0.10, edu_c))
        skill_c = 0.9 if document.skills else 0.0
        parts.append((0.15, skill_c))
        overall = round(sum(weight * value for weight, value in parts), 3)
        needs_review = overall < 0.7 or not document.candidate.contact.email
        return overall, needs_review
