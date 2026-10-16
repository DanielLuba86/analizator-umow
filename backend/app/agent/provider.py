"""Dostawca modelu (Claude API albo Microsoft Foundry): jedyne miejsce, które ich rozróżnia.

Agent (CLI Claude Code) wybiera dostawcę zmiennymi środowiskowymi, klasyfikator — klasą klienta
SDK. Dane logowania pochodzą wyłącznie z ustawień, nigdy z odczytu środowiska procesu.
"""

import anthropic

from app.config import Settings

_NO_CREDENTIALS = "brak danych logowania dostawcy"


def has_credentials(settings: Settings) -> bool:
    if settings.llm_provider == "foundry":
        return (
            settings.anthropic_foundry_api_key is not None
            and settings.anthropic_foundry_resource is not None
        )
    return settings.anthropic_api_key is not None


def agent_credentials_env(settings: Settings) -> dict[str, str]:
    """Zmienne dokładane do (wyczyszczonego) środowiska procesu agenta."""
    if not has_credentials(settings):
        raise ValueError(_NO_CREDENTIALS)
    if settings.llm_provider == "foundry":
        assert settings.anthropic_foundry_api_key and settings.anthropic_foundry_resource  # noqa: S101
        return {
            "CLAUDE_CODE_USE_FOUNDRY": "1",
            "ANTHROPIC_FOUNDRY_RESOURCE": settings.anthropic_foundry_resource,
            "ANTHROPIC_FOUNDRY_API_KEY": settings.anthropic_foundry_api_key.get_secret_value(),
        }
    assert settings.anthropic_api_key is not None  # noqa: S101
    return {"ANTHROPIC_API_KEY": settings.anthropic_api_key.get_secret_value()}


def classifier_client(
    settings: Settings,
) -> anthropic.AsyncAnthropic | anthropic.AsyncAnthropicFoundry:
    if not has_credentials(settings):
        raise ValueError(_NO_CREDENTIALS)
    if settings.llm_provider == "foundry":
        assert settings.anthropic_foundry_api_key and settings.anthropic_foundry_resource  # noqa: S101
        return anthropic.AsyncAnthropicFoundry(
            api_key=settings.anthropic_foundry_api_key.get_secret_value(),
            resource=settings.anthropic_foundry_resource,
            max_retries=settings.classifier_max_retries,
        )
    assert settings.anthropic_api_key is not None  # noqa: S101
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        max_retries=settings.classifier_max_retries,
    )
