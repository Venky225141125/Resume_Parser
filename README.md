# Hybrid Resume Parser

Deterministic-first resume parsing: extract, section, rules/taxonomy, validate, then optional LLM fallback. Phase 1 is scaffolding only — the parse pipeline is not implemented yet.

## Phase 1 status

| Capability | Status |
|---|---|
| Health / ready API | Implemented |
| Config, logging, errors, versions | Implemented |
| Parse pipeline | Contract only (`501 not_implemented`) |
| PDF/DOCX extraction | Next phase |
| LLM | Disabled stub |

## Setup

Python 3.12+ recommended.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://127.0.0.1:8000/api/v1/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

If `RESUME_PARSER_API_KEY` is set, send `X-API-Key` on parse/get routes. Health stays open.

## Tests

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

## Configuration

See `.env.example`. Secrets never belong in source.

PDF extraction (Phase 2) is planned with **PyMuPDF**. That library is AGPL unless you have a commercial license. The extractor interface is swappable if you need a permissive stack (pdfminer.six).

## License note

Application code in this repository is yours. Third-party packages keep their own licenses.
