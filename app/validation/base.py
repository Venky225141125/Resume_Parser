from abc import ABC, abstractmethod

from app.schemas.candidate import CandidateDocument


class Validator(ABC):
    @abstractmethod
    def validate(self, document: CandidateDocument) -> CandidateDocument:
        raise NotImplementedError
