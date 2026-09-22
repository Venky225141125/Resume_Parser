# Confidence scoring

Computed by `SourceConfidenceScorer` (`app/confidence/scorer.py`), wired into `ParsePipeline.parse_bytes` as the last pipeline stage before the response is returned.

| Source | Typical range | Notes |
|---|---|---|
| Exact email/URL regex | 0.95–0.99 | Format match only |
| Phone via phonenumbers | 0.90–0.97 | Valid parse |
| Skill taxonomy exact alias | 0.90–0.98 | Canonical map |
| Strong section heading | 0.85–0.95 | Taxonomy heading |
| Date pattern + order valid | 0.80–0.93 | No invented month |
| Heading-less section heuristic | 0.50–0.70 | Needs review if key fields missing |
| OCR word | Use engine score | Down-weight overall |
| LLM field | 0.40–0.80 after validation | Never trust raw JSON; must appear in excerpt |

Overall confidence is a weighted combination of required fields (contact, experience). `needs_review` if overall < 0.70 or any required field is ambiguous.
