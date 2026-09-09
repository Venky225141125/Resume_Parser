from app.core.versions import PARSER_VERSION, PHASE, SCHEMA_VERSION


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["parser_version"] == PARSER_VERSION
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["phase"] == PHASE
    assert body["llm_enabled"] is False


def test_ready_ok(client) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
