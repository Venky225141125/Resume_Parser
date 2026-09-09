# Architecture

Hybrid resume parser: cheapest reliable method first, LLM only on ambiguous slices.

## Current phase

**Phase 1 — scaffold.** Process boots, configuration and error contracts exist, health endpoints work. Parsing returns `501 not_implemented`.

## Pipeline (target)

```
file ingest → extractors → Document IR → layout → sections
    → field parsers → normalize → validate → confidence
        → high: JSON
        → low: LLM on excerpt → schema/business validation → JSON
```

## Layers

| Package | Role |
|---|---|
| `app.api` | HTTP only |
| `app.pipeline` | Orchestration |
| `app.extraction` | PDF/DOCX/TXT/OCR → `Document` |
| `app.layout` | Reading order / columns |
| `app.sections` | Canonical section map |
| `app.parsers` | Contact, experience, education, skills, … |
| `app.normalization` | Canonical values, keep raw |
| `app.validation` | Schema + business rules |
| `app.confidence` | Source-based scores |
| `app.llm` | Optional fallback (disabled stub) |
| `taxonomy/` | Extensible JSON, no code change |

## Defaults (approved)

- PDF engine later: PyMuPDF (AGPL); interface allows swap
- LLM v1: stub / disabled
- OCR and `.doc`: out of v1
- Auth: optional `X-API-Key` when env is set

## Versions

- `parser_version`: behavior of extraction
- `schema_version`: public JSON shape (`1.0`)

Do not log full resume text or PII. Structured logs use `document_id`, stage, duration, error code.
