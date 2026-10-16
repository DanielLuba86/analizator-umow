from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: `KLUCZ=` z .env.example oznacza „nie ustawiono”, nie pusty napis.
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    database_url: str
    anthropic_api_key: SecretStr | None = None
    agent_model: str = "claude-opus-5-5"
    classifier_model: str = "claude-haiku-5-5"
    agent_max_turns: int = 30
    agent_max_budget_usd: float = 0.50
    agent_max_findings: int = 60
    agent_timeout_s: int = 300
    max_contract_chars: int = 200_000
    max_body_bytes: int = 1_048_576  # ciało żądania; nginx ma ten sam limit (client_max_body_size)
    max_active_analyses: int = 5  # analizy queued/running naraz w całej aplikacji (koszt API)
    session_ttl_hours: int = 12
    cookie_secure: bool = True
    log_level: str = "INFO"
    seed_assistant_password: SecretStr | None = None
    seed_lawyer_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
