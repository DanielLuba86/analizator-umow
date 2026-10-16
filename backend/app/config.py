import re
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Reguła CLI Claude Code: 2–64 znaki, litery, cyfry i myślniki, bez myślnika na brzegach.
_FOUNDRY_RESOURCE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}[a-z0-9]")


class Settings(BaseSettings):
    # env_ignore_empty: `KLUCZ=` z .env.example oznacza „nie ustawiono”, nie pusty napis.
    # hide_input_in_errors: błąd walidacji nie może pokazać sekretu ani wartości z .env.
    model_config = SettingsConfigDict(
        extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    database_url: str
    anthropic_api_key: SecretStr | None = None
    # Dostawca modelu dla agenta i klasyfikatora (ADR 0009).
    llm_provider: Literal["anthropic", "foundry"] = "anthropic"
    anthropic_foundry_api_key: SecretStr | None = None
    anthropic_foundry_resource: str | None = None  # sama nazwa zasobu Foundry, nie URL
    # Nieobsługiwane: SDK `anthropic` czyta tę zmienną ze środowiska nawet przy `resource=`
    # i wtedy odmawia utworzenia klienta. Pole istnieje tylko po to, by odrzucić ją przy starcie.
    anthropic_foundry_base_url: str | None = None
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

    @field_validator("anthropic_foundry_base_url")
    @classmethod
    def _foundry_base_url_unsupported(cls, value: str | None) -> str | None:
        if value is not None:
            raise ValueError(
                "ANTHROPIC_FOUNDRY_BASE_URL nie jest obsługiwane; podaj ANTHROPIC_FOUNDRY_RESOURCE"
            )
        return value

    @field_validator("anthropic_foundry_resource")
    @classmethod
    def _foundry_resource_is_bare_name(cls, value: str | None) -> str | None:
        if value is not None and not _FOUNDRY_RESOURCE.fullmatch(value):
            raise ValueError("ANTHROPIC_FOUNDRY_RESOURCE: podaj samą nazwę zasobu Foundry")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
