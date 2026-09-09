import io

from app.core.config import clear_settings_cache
from app.core.logging import JsonFormatter, _redact
from app.main import create_app
from fastapi.testclient import TestClient


def test_parse_returns_501(client) -> None:
    files = {"file": ("resume.txt", io.BytesIO(b"Jane Doe\n"), "text/plain")}
    response = client.post("/api/v1/resumes/parse", files=files)
    assert response.status_code == 501
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "not_implemented"


def test_get_resume_returns_501(client) -> None:
    response = client.get("/api/v1/resumes/demo-id")
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"


def test_parse_rejects_oversized_file(monkeypatch) -> None:
    monkeypatch.setenv("RESUME_PARSER_MAX_UPLOAD_BYTES", "8")
    clear_settings_cache()
    with TestClient(create_app()) as local:
        files = {"file": ("resume.txt", io.BytesIO(b"0123456789"), "text/plain")}
        response = local.post("/api/v1/resumes/parse", files=files)
    clear_settings_cache()
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_parse_requires_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("RESUME_PARSER_API_KEY", "test-key")
    clear_settings_cache()
    files = {"file": ("resume.txt", io.BytesIO(b"hi"), "text/plain")}
    with TestClient(create_app()) as local:
        denied = local.post("/api/v1/resumes/parse", files=files)
        allowed = local.post(
            "/api/v1/resumes/parse",
            files=files,
            headers={"X-API-Key": "test-key"},
        )
        health = local.get("/api/v1/health")
    clear_settings_cache()
    assert denied.status_code == 401
    assert allowed.status_code == 501
    assert health.status_code == 200


def test_log_redaction_hides_resume_text() -> None:
    redacted = _redact({"document_id": "abc", "text": "secret resume", "stage": "extract"})
    assert redacted["text"] == "[redacted]"
    assert redacted["document_id"] == "abc"
    formatter = JsonFormatter()
    assert formatter.__class__.__name__ == "JsonFormatter"
