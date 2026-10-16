# ruff: noqa: S106
from typing import Any

import anthropic
import pytest
from pydantic import SecretStr

from app.agent.provider import agent_credentials_env, classifier_client, has_credentials
from app.config import Settings

URL = "postgresql+psycopg://u:p@localhost/db"


def _settings(**kw: Any) -> Settings:
    return Settings(database_url=URL, **kw)


FOUNDRY = {
    "llm_provider": "foundry",
    "anthropic_foundry_api_key": SecretStr("k-f"),
    "anthropic_foundry_resource": "moj-zasob",
}


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({"anthropic_api_key": SecretStr("sk-a")}, True),
        ({}, False),
        (FOUNDRY, True),
        ({**FOUNDRY, "anthropic_foundry_api_key": None}, False),
        ({**FOUNDRY, "anthropic_foundry_resource": None}, False),
        ({"llm_provider": "foundry", "anthropic_api_key": SecretStr("sk-a")}, False),
    ],
)
def test_has_credentials(kw: dict[str, Any], expected: bool) -> None:
    assert has_credentials(_settings(**kw)) is expected


def test_agent_env_anthropic() -> None:
    s = _settings(anthropic_api_key=SecretStr("sk-a"))
    assert agent_credentials_env(s) == {"ANTHROPIC_API_KEY": "sk-a"}


def test_agent_env_foundry() -> None:
    s = _settings(**FOUNDRY, anthropic_api_key=SecretStr("sk-a"))
    assert agent_credentials_env(s) == {
        "CLAUDE_CODE_USE_FOUNDRY": "1",
        "ANTHROPIC_FOUNDRY_RESOURCE": "moj-zasob",
        "ANTHROPIC_FOUNDRY_API_KEY": "k-f",
    }


def test_agent_env_without_credentials_raises() -> None:
    with pytest.raises(ValueError, match="brak danych logowania"):
        agent_credentials_env(_settings(llm_provider="foundry"))


def test_classifier_client_foundry() -> None:
    c = classifier_client(_settings(**FOUNDRY))
    assert isinstance(c, anthropic.AsyncAnthropicFoundry)
    assert str(c.base_url) == "https://moj-zasob.services.ai.azure.com/anthropic/"
    assert c.api_key == "k-f"


def test_classifier_client_anthropic() -> None:
    c = classifier_client(_settings(anthropic_api_key=SecretStr("sk-a")))
    assert type(c) is anthropic.AsyncAnthropic
    assert c.api_key == "sk-a"


def test_classifier_client_without_credentials_raises() -> None:
    with pytest.raises(ValueError, match="brak danych logowania"):
        classifier_client(_settings())


@pytest.mark.parametrize("kw", [{"anthropic_api_key": SecretStr("sk-a")}, FOUNDRY])
def test_classifier_client_retries_from_settings(kw: dict[str, Any]) -> None:
    assert classifier_client(_settings(**kw)).max_retries == 5
    assert classifier_client(_settings(**kw, classifier_max_retries=7)).max_retries == 7
