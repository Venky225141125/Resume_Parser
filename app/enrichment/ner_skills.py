"""Transformer skill extractor (optional).

Wraps a Hugging Face token-classification model such as
`jjzha/jobbert_skill_extraction` so it can add the skills a gazetteer
structurally cannot hold: unnamed domain phrases like "escalation handling"
or "biopsychosocial assessment", which are real skills but are not products
and will never appear in a dictionary of named technologies.

`transformers` and `torch` are NOT base dependencies — they are roughly two
orders of magnitude larger than everything else this service installs, and
inference costs ~1-3s per resume on CPU against ~0.8s for the whole
deterministic parse. So this module imports them lazily, inside the call that
needs them, and reports `available() is False` when they are absent. Enabling
it is a deliberate deployment choice: see requirements-ml.txt.
"""

from __future__ import annotations

import threading
from typing import Any

import logging

from app.core.logging import log_event
from app.enrichment.base import ExtractedSpan

logger = logging.getLogger(__name__)

# Entity labels used by the SkillSpan/ESCO family of models.
_SKILL_LABELS = {"SKILL", "KNOWLEDGE", "B-SKILL", "I-SKILL", "LABEL_1", "LABEL_2"}


class TransformerSkillExtractor:
    """Skill NER over resume text, loaded lazily and failing soft."""

    def __init__(
        self,
        model: str,
        *,
        min_score: float = 0.6,
        max_chars: int = 20000,
        device: int = -1,
    ) -> None:
        self._model = model
        self._min_score = min_score
        self._max_chars = max_chars
        self._device = device
        self._pipeline: Any | None = None
        self._load_failed = False
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "ner"

    def available(self) -> bool:
        if self._load_failed:
            return False
        if self._pipeline is not None:
            return True
        return self._load() is not None

    def _load(self) -> Any | None:
        """Build the HF pipeline once. Guarded by a lock because the first
        request to touch it may arrive on several worker threads at once."""
        with self._lock:
            if self._pipeline is not None or self._load_failed:
                return self._pipeline
            try:
                from transformers import pipeline  # imported lazily: heavy, optional
            except ImportError:
                log_event(
                    logger,
                    "skill_ner_unavailable",
                    reason="transformers_not_installed",
                    model=self._model,
                )
                self._load_failed = True
                return None
            try:
                self._pipeline = pipeline(
                    "token-classification",
                    model=self._model,
                    aggregation_strategy="simple",
                    device=self._device,
                )
            except Exception as exc:  # noqa: BLE001 - never fail a parse on this
                log_event(
                    logger,
                    "skill_ner_load_failed",
                    model=self._model,
                    error=type(exc).__name__,
                )
                self._load_failed = True
                return None
            return self._pipeline

    def extract(self, text: str) -> list[ExtractedSpan]:
        if not text.strip():
            return []
        engine = self._load()
        if engine is None:
            return []
        # Resume text is unbounded but model context is not; the tail of a
        # long resume is publications and references, not skills.
        payload = text[: self._max_chars]
        try:
            raw = engine(payload)
        except Exception as exc:  # noqa: BLE001 - enrichment must never fail a parse
            log_event(
                logger,
                "skill_ner_inference_failed",
                model=self._model,
                error=type(exc).__name__,
            )
            return []
        return _to_spans(raw, self._min_score)


def _to_spans(raw: Any, min_score: float) -> list[ExtractedSpan]:
    """Normalize the pipeline's output into spans.

    Different checkpoints label skills differently ("SKILL", "KNOWLEDGE", or
    bare "LABEL_1" when the checkpoint ships no id2label map), so an entity
    group that is not recognizably *not* a skill is kept rather than dropped.
    """
    spans: list[ExtractedSpan] = []
    seen: set[str] = set()
    for entity in raw or []:
        if not isinstance(entity, dict):
            continue
        group = str(entity.get("entity_group") or entity.get("entity") or "").upper()
        if group and group not in _SKILL_LABELS and group not in {"", "LABEL_0", "O"}:
            continue
        if group in {"LABEL_0", "O"}:
            continue
        text = str(entity.get("word") or "").strip(" ,;:.-•")
        score = float(entity.get("score") or 0.0)
        if not text or score < min_score:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        spans.append(ExtractedSpan(text=text, score=score))
    return spans
