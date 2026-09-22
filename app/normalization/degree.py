"""Canonicalize degree text to a small fixed set of labels, independent of
how the raw degree string was extracted (regex today, LLM later)."""

from __future__ import annotations

import re

from app.normalization.base import Normalizer

_DEGREE_NORM: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ph\.?d|doctorate", re.I), "PhD"),
    (re.compile(r"\bmba\b", re.I), "MBA"),
    (re.compile(r"master(?:'s)?\s+of\s+technology|m\.?\s*tech", re.I), "M.Tech"),
    (re.compile(r"bachelor(?:'s)?\s+of\s+technology|b\.?\s*tech", re.I), "B.Tech"),
    (re.compile(r"m\.?\s*e\.?\b", re.I), "M.E."),
    (re.compile(r"b\.?\s*e\.?\b", re.I), "B.E."),
    (re.compile(r"m\.?\s*sc", re.I), "M.Sc"),
    (re.compile(r"b\.?\s*sc", re.I), "B.Sc"),
    (re.compile(r"\bmca\b", re.I), "MCA"),
    (re.compile(r"\bbca\b", re.I), "BCA"),
    (re.compile(r"master(?:'s)?", re.I), "Master's"),
    (re.compile(r"bachelor(?:'s)?", re.I), "Bachelor's"),
    (re.compile(r"associate", re.I), "Associate"),
    (re.compile(r"diploma", re.I), "Diploma"),
    (re.compile(r"high school", re.I), "High School"),
]


class DegreeNormalizer(Normalizer):
    """Maps a raw degree string (e.g. "Bachelor of Science") to a canonical
    label (e.g. "B.Sc"). Falls back to the raw value when no pattern matches
    — never invents a degree that wasn't in the source text."""

    def normalize(self, raw: str) -> str:
        for pattern, label in _DEGREE_NORM:
            if pattern.search(raw):
                return label
        return raw
