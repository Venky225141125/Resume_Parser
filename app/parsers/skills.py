from __future__ import annotations

import re

from app.enrichment.base import SkillExtractor
from app.normalization.skills import SkillNormalizer
from app.parsers.base import FieldParser
from app.parsers.support import combined_text, section_lines, split_label_prefix
from app.schemas.candidate import SkillItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_SPLIT = re.compile(r"[,;|•●\n]+")
_MAX_SKILL_WORDS = 4
# NER models happily return whole clauses; a skill is a phrase, not a sentence.
_MAX_NER_SKILL_WORDS = 6
_SKILL_SECTIONS = ("skills", "summary", "experience", "projects")


class SkillsParser(FieldParser):
    def __init__(self, extractor: SkillExtractor | None = None) -> None:
        # Injected for tests; in the pipeline it comes from configuration and
        # is None unless skill NER is explicitly enabled.
        self._extractor = extractor

    def parse(self, document: Document, sections: list[DetectedSection]) -> list[SkillItem]:
        normalizer = SkillNormalizer()
        items: list[SkillItem] = []
        seen: set[str] = set()

        for token in _tokens(normalizer, section_lines(sections, "skills")):
            item = normalizer.match_token(token)
            _add(normalizer, items, seen, item)

        _harvest(normalizer, items, seen, combined_text(sections, "skills"), 0.9)

        # Always sweep the whole resume so skills used only in experience,
        # summary, project or "Environment:" lines are reported too — most
        # resumes name far more of their skills in the work history than in
        # the Skills block, and many have no Skills block at all.
        _harvest(normalizer, items, seen, document.plain_text(), 0.78)

        for line in section_lines(sections, *_SKILL_SECTIONS):
            if not line.lower().startswith("environment:"):
                continue
            _, remainder = split_label_prefix(line)
            for token in _SPLIT.split(remainder):
                cleaned = token.strip(" -•*")
                if not cleaned:
                    continue
                _add(normalizer, items, seen, normalizer.match_token(cleaned))

        _enrich(normalizer, items, seen, document, self._extractor)
        return items


def _enrich(
    normalizer: SkillNormalizer,
    items: list[SkillItem],
    seen: set[str],
    document: Document,
    extractor: SkillExtractor | None,
) -> None:
    """Add skills a statistical extractor found that the rules did not.

    Runs last and only appends: a gazetteer cannot hold unnamed domain
    phrases ("escalation handling", "biopsychosocial assessment") because
    they are not products, but everything already matched deterministically
    keeps its higher-confidence, explainable entry. Anything the extractor
    returns that *is* in the taxonomy is canonicalized like any other token,
    so the same skill never appears twice under two spellings.
    """
    if extractor is None:
        return
    for span in extractor.extract(document.plain_text()):
        token = span.text.strip()
        if not token or len(token.split()) > _MAX_NER_SKILL_WORDS:
            continue
        item = normalizer.match_token(token)
        if item.source != "taxonomy":
            # Not a known skill: keep the model's own text and score, and
            # label the source so an unverified span is distinguishable from
            # a taxonomy match in the output.
            item = SkillItem(
                raw=token,
                normalized=token,
                category=None,
                confidence=round(span.score, 3),
                source=extractor.name,
            )
        _add(normalizer, items, seen, item)


def _harvest(
    normalizer: SkillNormalizer,
    items: list[SkillItem],
    seen: set[str],
    blob: str,
    confidence: float,
) -> None:
    """Add every taxonomy skill named anywhere in `blob`."""
    if not blob:
        return
    for alias in normalizer.find_aliases(blob):
        hit = normalizer.mapping.get(alias)
        if hit is None:
            continue
        canonical, category = hit
        if canonical.lower() in seen:
            continue
        _add(
            normalizer,
            items,
            seen,
            SkillItem(
                raw=alias,
                normalized=canonical,
                category=category,
                confidence=confidence,
                source="taxonomy",
            ),
        )


def _add(normalizer: SkillNormalizer, items: list[SkillItem], seen: set[str], item: SkillItem) -> None:
    key = (item.normalized or item.raw).lower()
    if key in seen or normalizer.is_noise_or_label(key) or normalizer.is_noise_or_label(item.raw):
        return
    seen.add(key)
    items.append(item)


def _tokens(normalizer: SkillNormalizer, lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        _, remainder = split_label_prefix(line)
        if normalizer.is_noise_or_label(remainder):
            continue
        parts = _SPLIT.split(remainder)
        for part in parts:
            cleaned = part.strip(" -•*")
            if not cleaned or normalizer.is_noise_or_label(cleaned):
                continue
            if len(cleaned.split()) > _MAX_SKILL_WORDS:
                continue
            tokens.append(cleaned)
    return tokens
