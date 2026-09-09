from urllib.parse import urlparse

from app.schemas.candidate import CandidateDocument
from app.validation.base import Validator


class CandidateValidator(Validator):
    def validate(self, document: CandidateDocument) -> CandidateDocument:
        contact = document.candidate.contact
        if contact.email and "@" not in contact.email:
            contact.email = None
        document.candidate.links = [
            link for link in document.candidate.links if _valid_url(link.url)
        ]
        for item in document.experience:
            if item.start_date and item.end_date and item.start_date > item.end_date:
                item.end_date = None
                item.confidence = min(item.confidence or 0.5, 0.45)
        for item in document.education:
            if item.start_date and item.end_date and item.start_date > item.end_date:
                item.end_date = None
        for item in document.projects:
            if item.url and not _valid_url(item.url):
                item.url = None
        for item in document.certifications:
            if item.credential_url and not _valid_url(item.credential_url):
                item.credential_url = None
        return document


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
