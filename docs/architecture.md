# Architecture

Hybrid resume parser: cheapest reliable method first, LLM only on ambiguous slices.

## Current phase

**Pipeline wired end-to-end for text-based PDF/DOCX/TXT.** `POST /resumes/parse` runs the full deterministic pipeline and persists the result; `GET /resumes/{id}` reads it back. LLM fallback is still a disabled stub (never invoked), and OCR routing for scanned PDFs is not implemented yet — `needs_ocr` is detected during PDF extraction but nothing consumes it.

## Pipeline (current)

```
file ingest → extractors → Document IR → layout → sections
    → field parsers → normalize → validate → confidence
        → high/medium: JSON
        → low: (LLM fallback not yet implemented)
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
