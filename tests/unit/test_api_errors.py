import io

from app.core.config import clear_settings_cache
from app.core.logging import JsonFormatter, _redact
from app.main import create_app
from fastapi.testclient import TestClient


def test_parse_returns_parsed_candidate_and_can_be_fetched_back(client) -> None:
    files = {
        "file": (
            "resume.txt",
            io.BytesIO(b"Jane Doe\njane.doe@example.com\n"),
            "text/plain",
        )
    }
    response = client.post("/api/v1/resumes/parse", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["candidate"]["contact"]["email"] == "jane.doe@example.com"

    fetched = client.get(f"/api/v1/resumes/{body['document_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["document_id"] == body["document_id"]


def test_get_resume_returns_404_when_unknown(client) -> None:
    response = client.get("/api/v1/resumes/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_ui_page_is_served(client) -> None:
    response = client.get("/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Resume Parser" in response.text
    assert "/api/v1/resumes/parse" in response.text


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
    assert allowed.status_code == 200
    assert health.status_code == 200


def test_log_redaction_hides_resume_text() -> None:
    redacted = _redact({"document_id": "abc", "text": "secret resume", "stage": "extract"})
    assert redacted["text"] == "[redacted]"
    assert redacted["document_id"] == "abc"
    formatter = JsonFormatter()
    assert formatter.__class__.__name__ == "JsonFormatter"
