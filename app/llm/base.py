from abc import ABC, abstractmethod
from typing import Any


class LlmFallback(ABC):
    """Optional slice-level fallback. Disabled in Phase 1."""

    @abstractmethod
    def should_invoke(self, reason: str, payload: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def complete(self, prompt: str, excerpt: str) -> dict[str, Any]:
        raise NotImplementedError
