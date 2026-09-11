from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.document import Block, Document, Line
from app.sections.base import DetectedSection, SectionDetector
from app.taxonomy_data import load_section_taxonomy

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_SPACES = re.compile(r"\s+")

# Labels that appear *inside* a Technical Skills table (Languages / Tools /
# Databases / …). They must not open a new canonical section — especially
# "Languages", which otherwise swallows the rest of the resume as spoken
# languages.
_SKILL_CATEGORY_LABELS = {
    "languages",
    "programming languages",
    "tools",
    "databases",
    "database",
    "web servers",
    "web services",
    "methodologies",
    "operating systems",
    "frameworks",
    "libraries",
    "technologies",
    "environment",
}


@dataclass(slots=True)
class _HeadingHit:
    canonical: str
    title_raw: str
    confidence: float
    before: str
    after: str


class TaxonomySectionDetector(SectionDetector):
    def __init__(self, taxonomy: dict[str, list[str]] | None = None) -> None:
        self._taxonomy = taxonomy or load_section_taxonomy()
        self._alias_to_canonical: dict[str, str] = {}
        for canonical, aliases in self._taxonomy.items():
            self._alias_to_canonical[_normalize(canonical)] = canonical
            for alias in aliases:
                self._alias_to_canonical[_normalize(alias)] = canonical
        self._alias_pattern = _compile_alias_pattern(self._alias_to_canonical)

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
            hit = self._match_heading(block, current.canonical)
            if hit is None:
                current.blocks.append(block)
                continue
            if hit.before.strip():
                current.blocks.append(_block_with_text(block, hit.before))
            found_named = True
            if current.blocks or current.canonical != "header":
                sections.append(current)
            current = DetectedSection(
                canonical=hit.canonical,
                title_raw=hit.title_raw,
                confidence=hit.confidence,
                blocks=[],
            )
            if hit.after.strip():
                current.blocks.append(_block_with_text(block, hit.after))
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

    def _match_heading(self, block: Block, current_canonical: str) -> _HeadingHit | None:
        raw = block.text.strip()
        if not raw:
            return None
        hit = self._exact_heading(block, raw)
        if hit is None:
            hit = self._prefix_heading(raw, block.block_type)
        if hit is None:
            hit = self._inline_colon_heading(raw)
        if hit is None:
            hit = self._trailing_heading(raw)
        if hit is None:
            return None
        if _is_skill_category(hit.canonical, hit.title_raw, current_canonical):
            return None
        return hit

    def _exact_heading(self, block: Block, raw: str) -> _HeadingHit | None:
        if len(raw) > 80:
            return None
        normalized = _normalize(raw)
        if not normalized:
            return None
        if len(normalized.split()) <= 6:
            canonical = self._alias_to_canonical.get(normalized)
            if canonical:
                confidence = 0.93 if block.block_type == "heading" else 0.86
                return _HeadingHit(canonical, raw, confidence, "", "")
        if block.block_type == "heading" and len(normalized.split()) <= 8:
            canonical = self._contains_alias(normalized)
            if canonical:
                return _HeadingHit(canonical, raw, 0.75, "", "")
        return None

    def _prefix_heading(self, raw: str, block_type: str) -> _HeadingHit | None:
        match = self._alias_pattern.match(raw)
        if not match:
            return None
        alias = match.group(1)
        canonical = self._alias_to_canonical.get(_normalize(alias))
        if not canonical:
            return None
        after = raw[match.end() :].lstrip(" :-–—")
        if not after and len(_normalize(raw).split()) <= 6:
            # Exact headings are handled above; avoid double-matching.
            return None
        if after and not (match.group(0).rstrip().endswith(":") or len(alias.split()) >= 2):
            # "Experience in Core Java" is prose, not a section title.
            return None
        confidence = 0.9 if block_type == "heading" else 0.84
        return _HeadingHit(canonical, alias.strip(" :"), confidence, "", after)

    def _inline_colon_heading(self, raw: str) -> _HeadingHit | None:
        # "Java Developer +1-555-0100 Professional Summary:" glued on one line.
        for match in self._alias_pattern.finditer(raw):
            if match.start() == 0:
                continue
            if not match.group(0).rstrip().endswith(":"):
                continue
            alias = match.group(1)
            canonical = self._alias_to_canonical.get(_normalize(alias))
            if not canonical:
                continue
            before = raw[: match.start()].strip(" |,-")
            after = raw[match.end() :].lstrip(" :-–—")
            if len(before) < 8:
                continue
            return _HeadingHit(canonical, alias.strip(" :"), 0.82, before, after)
        return None

    def _trailing_heading(self, raw: str) -> _HeadingHit | None:
        # "Environment: Java, Spring, Git Education" — last token is a heading.
        if "," not in raw and "environment:" not in raw.lower():
            return None
        words = raw.split()
        if len(words) < 6:
            return None
        for count in (3, 2, 1):
            tail = " ".join(words[-count:])
            canonical = self._alias_to_canonical.get(_normalize(tail))
            if not canonical:
                continue
            before = " ".join(words[:-count]).strip(" |,-")
            if len(before.split()) < 4:
                continue
            return _HeadingHit(canonical, tail, 0.8, before, "")
        return None

    def _contains_alias(self, normalized: str) -> str | None:
        padded = f" {normalized} "
        best: tuple[str, str] | None = None
        for alias_norm, canonical in self._alias_to_canonical.items():
            if f" {alias_norm} " in padded and (best is None or len(alias_norm) > len(best[1])):
                best = (canonical, alias_norm)
        return best[0] if best else None


def _is_skill_category(canonical: str, title_raw: str, current_canonical: str) -> bool:
    if current_canonical != "skills":
        return False
    label = _normalize(title_raw)
    return label in _SKILL_CATEGORY_LABELS or canonical == "languages"


def _compile_alias_pattern(alias_to_canonical: dict[str, str]) -> re.Pattern[str]:
    aliases = sorted({alias for alias in alias_to_canonical if len(alias) >= 5}, key=len, reverse=True)
    body = "|".join(re.escape(alias) for alias in aliases)
    return re.compile(rf"(?i)(?<![A-Za-z0-9])({body})(\s*:)?")


def _block_with_text(block: Block, text: str) -> Block:
    cleaned = text.strip()
    line = Line(text=cleaned, page=block.page, bbox=block.bbox, confidence=block.confidence)
    return Block(
        text=cleaned,
        page=block.page,
        bbox=block.bbox,
        block_type="paragraph",
        column=block.column,
        confidence=block.confidence,
        lines=[line],
    )


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    cleaned = _NON_ALNUM.sub(" ", lowered)
    return _SPACES.sub(" ", cleaned).strip()
