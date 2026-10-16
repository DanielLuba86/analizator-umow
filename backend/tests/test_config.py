import pytest
from pydantic import ValidationError

from app.config import Settings

URL = "postgresql+psycopg://u:p@localhost/db"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_settings_defaults() -> None:
    s = Settings(database_url=URL)
    assert s.anthropic_api_key is None
    assert (s.agent_model, s.classifier_model) == ("claude-opus-5-5", "claude-haiku-5-5")
    assert (s.agent_max_turns, s.agent_max_budget_usd, s.agent_max_findings) == (30, 0.50, 60)
    assert s.agent_timeout_s == 300
    assert s.max_contract_chars == 200_000
    assert s.max_body_bytes == 1_048_576
    assert s.max_active_analyses == 5
    assert s.session_ttl_hours == 12
    assert s.cookie_secure is True  # bezpieczne domyślnie; lokalne HTTP wyłącza je w .env
    assert s.log_level == "INFO"
    assert s.llm_provider == "anthropic"
    assert (s.anthropic_foundry_api_key, s.anthropic_foundry_resource) == (None, None)


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("AGENT_MAX_TURNS", "5")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("MAX_ACTIVE_ANALYSES", "2")
    s = Settings()  # type: ignore[call-arg]
    assert (s.database_url, s.agent_max_turns, s.cookie_secure, s.max_active_analyses) == (
        URL,
        5,
        False,
        2,
    )


def test_empty_env_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """.env.example ma `ANTHROPIC_API_KEY=` — pusty klucz to brak klucza, nie klucz ''."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("SEED_LAWYER_PASSWORD", "")
    s = Settings(database_url=URL)
    assert s.anthropic_api_key is None
    assert s.seed_lawyer_password is None


def test_foundry_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "foundry")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_RESOURCE", "moj-zasob")
    s = Settings(database_url=URL)
    assert s.llm_provider == "foundry"
    assert s.anthropic_foundry_api_key is not None
    assert s.anthropic_foundry_api_key.get_secret_value() == "k"
    assert s.anthropic_foundry_resource == "moj-zasob"


@pytest.mark.parametrize(
    "resource",
    [
        "https://moj-zasob.services.ai.azure.com/anthropic",
        "moj-zasob.services.ai.azure.com",
        "Moj-Zasob",
        "moj-zasob ",
    ],
)
def test_foundry_resource_rejects_url_host_uppercase_and_trailing_space(resource: str) -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(database_url=URL, anthropic_foundry_resource=resource)
    assert "samą nazwę zasobu" in str(exc.value)
    assert resource.strip() not in str(exc.value)


def test_empty_foundry_resource_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_RESOURCE", "")
    assert Settings(database_url=URL).anthropic_foundry_resource is None


@pytest.mark.parametrize("provider", ["bedrock", "Foundry"])
def test_unknown_or_capitalized_provider_rejected(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    with pytest.raises(ValidationError):
        Settings(database_url=URL)
