from typing import Any

from app.core.config import Settings
from app.llm.base import LlmFallback


class DisabledLlmFallback(LlmFallback):
    """Deterministic no-op until Phase 9."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.llm_enabled

    def should_invoke(self, reason: str, payload: Any) -> bool:
        return False

    def complete(self, prompt: str, excerpt: str) -> dict[str, Any]:
        raise RuntimeError("LLM fallback is disabled.")
