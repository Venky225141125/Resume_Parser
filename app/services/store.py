from abc import ABC, abstractmethod

from app.schemas.candidate import ParseResponse


class ResultStore(ABC):
    @abstractmethod
    def save(self, result: ParseResponse) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str) -> ParseResponse | None:
        raise NotImplementedError


class InMemoryResultStore(ResultStore):
    def __init__(self) -> None:
        self._items: dict[str, ParseResponse] = {}

    def save(self, result: ParseResponse) -> None:
        self._items[result.document_id] = result

    def get(self, document_id: str) -> ParseResponse | None:
        return self._items.get(document_id)
