from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="RESUME_PARSER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    api_key: str | None = None
    max_upload_bytes: int = 10 * 1024 * 1024
    request_timeout_seconds: float = 60.0
    database_url: str = "sqlite:///./data/resume_parser.db"
    retention_days: int = 30
    # Optional layer-3 skill NER. Off by default: it needs transformers and
    # torch, which dwarf every other dependency, and adds ~1-3s per resume on
    # CPU against ~0.8s for the whole deterministic parse. It only ever adds
    # skills the gazetteer missed; it never overrides a deterministic result.
    skill_ner_enabled: bool = False
    skill_ner_model: str = "jjzha/jobbert_skill_extraction"
    skill_ner_min_score: float = 0.6
    skill_ner_max_chars: int = 20000
    skill_ner_device: int = -1  # -1 = CPU; a CUDA device index to use a GPU
    llm_enabled: bool = False
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def api_auth_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
