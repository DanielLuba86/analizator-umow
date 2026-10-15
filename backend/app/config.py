from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    anthropic_api_key: SecretStr | None = None
    agent_model: str = "claude-opus-5-5"
    classifier_model: str = "claude-haiku-5-5"
    agent_max_turns: int = 30
    agent_max_budget_usd: float = 0.50
    agent_max_findings: int = 60
    agent_timeout_s: int = 300
    max_contract_chars: int = 200_000
    session_ttl_hours: int = 12
    cookie_secure: bool = True
    log_level: str = "INFO"
    seed_assistant_password: SecretStr | None = None
    seed_lawyer_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
