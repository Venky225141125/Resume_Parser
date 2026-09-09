from __future__ import annotations

import re

from app.sections.base import DetectedSection, SectionDetector
from app.schemas.document import Block, Document
from app.taxonomy_data import load_section_taxonomy

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_SPACES = re.compile(r"\s+")


class TaxonomySectionDetector(SectionDetector):
    def __init__(self, taxonomy: dict[str, list[str]] | None = None) -> None:
        self._taxonomy = taxonomy or load_section_taxonomy()
        self._alias_to_canonical: dict[str, str] = {}
        for canonical, aliases in self._taxonomy.items():
            self._alias_to_canonical[_normalize(canonical)] = canonical
            for alias in aliases:
                self._alias_to_canonical[_normalize(alias)] = canonical

    def detect(self, document: Document) -> list[DetectedSection]:
        usable = [
            block
            for block in document.blocks
            if block.text.strip() and block.block_type not in {"header", "footer"}
        ]
        sections: list[DetectedSection] = []
        current = DetectedSection(canonical="header", title_raw=None, confidence=0.55, blocks=[])
        found_named = False
        for block in usable:
            mapped = self._match_heading(block)
            if mapped:
                found_named = True
                if current.blocks or current.canonical != "header":
                    sections.append(current)
                canonical, raw, confidence = mapped
                current = DetectedSection(
                    canonical=canonical,
                    title_raw=raw,
                    confidence=confidence,
                    blocks=[],
                )
                continue
            current.blocks.append(block)
        if current.blocks or current.canonical != "header":
            sections.append(current)
        if not found_named:
            body_blocks = [block for section in sections for block in section.blocks]
            return [
                DetectedSection(
                    canonical="body",
                    title_raw=None,
                    confidence=0.4,
                    blocks=body_blocks,
                )
            ]
        return sections

    def _match_heading(self, block: Block) -> tuple[str, str, float] | None:
        raw = block.text.strip()
        if not raw or len(raw) > 80:
            return None
        normalized = _normalize(raw)
        if not normalized:
            return None
        if len(normalized.split()) <= 6:
            canonical = self._alias_to_canonical.get(normalized)
            if canonical:
                confidence = 0.93 if block.block_type == "heading" else 0.86
                return canonical, raw, confidence
        # Real resumes phrase headings creatively ("VCU Practical Experience:",
        # "Personal Accomplishments", "Key Skills and Software") — an exact
        # alias match misses these. Fall back to "contains a known alias as a
        # whole phrase", but only for blocks already styled like a heading
        # (font-size promoted), so an ordinary sentence that happens to
        # mention "experience" or "education" in passing doesn't get read as
        # a new section boundary.
        if block.block_type == "heading" and len(normalized.split()) <= 8:
            canonical = self._contains_alias(normalized)
            if canonical:
                return canonical, raw, 0.75
        return None

    def _contains_alias(self, normalized: str) -> str | None:
        padded = f" {normalized} "
        best: tuple[str, str] | None = None
        for alias_norm, canonical in self._alias_to_canonical.items():
            if f" {alias_norm} " in padded and (best is None or len(alias_norm) > len(best[1])):
                best = (canonical, alias_norm)
        return best[0] if best else None


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    cleaned = _NON_ALNUM.sub(" ", lowered)
    return _SPACES.sub(" ", cleaned).strip()
