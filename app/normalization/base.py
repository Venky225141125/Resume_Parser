from abc import ABC, abstractmethod
from typing import Any


class Normalizer(ABC):
    @abstractmethod
    def normalize(self, payload: Any) -> Any:
        raise NotImplementedError
