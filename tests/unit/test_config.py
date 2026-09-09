from app.core.config import Settings, clear_settings_cache, get_settings


def test_default_settings_disable_llm_and_auth(monkeypatch) -> None:
    monkeypatch.delenv("RESUME_PARSER_API_KEY", raising=False)
    monkeypatch.delenv("RESUME_PARSER_LLM_ENABLED", raising=False)
    clear_settings_cache()
    settings = get_settings()
    assert settings.llm_enabled is False
    assert settings.api_auth_enabled is False
    assert settings.max_upload_bytes == 10 * 1024 * 1024


def test_api_auth_enabled_when_key_set() -> None:
    settings = Settings(api_key="secret")
    assert settings.api_auth_enabled is True
