import pytest

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
