# ruff: noqa: S105, S106
import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import structlog.testing
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLIConnectionError,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
)
from pydantic import SecretStr

from app.agent.context import AnalysisContext
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.sdk_runner import (
    ALLOWED_TOOLS,
    SERVER_NAME,
    SdkAgentRunner,
    UnexpectedToolset,
    build_mcp_server,
    build_options,
    build_sdk_tools,
    check_init_tools,
    outcome_from_result,
    start_prompt,
)
from app.config import Settings


@pytest.fixture(autouse=True)
def _tempdir_in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build_options tworzy katalog roboczy agenta; w testach trafia do tmp_path."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))


CTX = AnalysisContext(analysis_id=1, version_id=2, kind="najem", max_findings=60)


def _settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "anthropic_api_key": SecretStr("sk-test-klucz"),
        "agent_max_turns": 7,
        "agent_max_budget_usd": 0.25,
        "agent_timeout_s": 5,
    }
    base.update(kw)
    return Settings(**base)


class RecordingTools:
    """Atrapa AgentTools: zapisuje wywołania, zwraca stały wynik."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        async def method(**kwargs: Any) -> dict[str, Any]:
            self.calls.append((name, kwargs))
            return {"content": [{"type": "text", "text": "ok"}], "is_error": False}

        return method


def _options(settings: Settings | None = None) -> ClaudeAgentOptions:
    s = settings or _settings()
    return build_options(s, build_mcp_server(RecordingTools()))  # type: ignore[arg-type]


def _result(subtype: str, *, is_error: bool = False, cost: float | None = 0.12) -> ResultMessage:
    return ResultMessage(
        subtype=subtype,
        duration_ms=10,
        duration_api_ms=5,
        is_error=is_error,
        num_turns=4,
        session_id="s",
        total_cost_usd=cost,
    )


def _init(tools: list[str]) -> SystemMessage:
    return SystemMessage(subtype="init", data={"type": "system", "subtype": "init", "tools": tools})


def test_options_disable_builtin_tools() -> None:
    assert _options().tools == []


def test_options_allow_only_own_tools() -> None:
    opts = _options()
    assert opts.allowed_tools == ALLOWED_TOOLS
    assert ALLOWED_TOOLS == [
        "mcp__umowy__list_fragments",
        "mcp__umowy__read_fragment",
        "mcp__umowy__search_templates",
        "mcp__umowy__submit_finding",
        "mcp__umowy__request_action",
    ]
    assert opts.permission_mode == "dontAsk"
    assert isinstance(opts.mcp_servers, dict) and list(opts.mcp_servers) == [SERVER_NAME]
    assert opts.system_prompt == SYSTEM_PROMPT


def test_options_no_filesystem_settings() -> None:
    opts = _options()
    assert opts.setting_sources == []
    assert opts.cwd is not None
    cwd = Path(opts.cwd)
    assert cwd.is_dir() and list(cwd.iterdir()) == []


def test_options_limits_from_settings() -> None:
    opts = _options(_settings(agent_model="claude-test-model"))
    assert opts.model == "claude-test-model"
    assert opts.max_turns == 7
    assert opts.max_budget_usd == 0.25


def test_env_sets_only_api_key_and_blanks_inherited_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SDK dokleja os.environ do procesu CLI; nadpisujemy sekrety pustymi wartościami."""
    for name in list(os.environ):
        monkeypatch.delenv(name)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:haslo@db/x")
    monkeypatch.setenv("SEED_LAWYER_PASSWORD", "haslo")
    monkeypatch.setenv("POSTGRES_PASSWORD", "haslo")
    monkeypatch.setenv("SOME_API_SECRET", "x")
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "klucz-z-otoczenia")
    assert _options().env == {
        "ANTHROPIC_API_KEY": "sk-test-klucz",
        "DATABASE_URL": "",
        "SEED_LAWYER_PASSWORD": "",
        "POSTGRES_PASSWORD": "",
        "SOME_API_SECRET": "",
        "GH_TOKEN": "",
    }


def test_build_options_requires_api_key() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        _options(_settings(anthropic_api_key=None))


def test_start_prompt_has_kind_and_no_contract_text() -> None:
    assert start_prompt(CTX) == "Przeanalizuj umowę rodzaju najem. Zacznij od list_fragments."


@pytest.mark.parametrize(
    ("subtype", "is_error", "status", "reason"),
    [
        ("success", False, "done", None),
        ("success", True, "failed", "api_error"),
        ("error_max_turns", True, "budget_exceeded", "turns"),
        ("error_max_budget_usd", True, "budget_exceeded", "budget"),
        ("error_during_execution", True, "failed", "error_during_execution"),
        ("something_new", True, "failed", "something_new"),
    ],
)
def test_result_subtype_mapping(
    subtype: str, is_error: bool, status: str, reason: str | None
) -> None:
    out = outcome_from_result(_result(subtype, is_error=is_error))
    assert (out.status, out.reason, out.turns, out.cost_usd) == (status, reason, 4, 0.12)


def test_result_without_cost_is_zero() -> None:
    assert outcome_from_result(_result("success", cost=None)).cost_usd == 0


def test_check_init_tools_accepts_exactly_five() -> None:
    check_init_tools(list(reversed(ALLOWED_TOOLS)))


def test_check_init_tools_rejects_builtin_extra() -> None:
    with pytest.raises(UnexpectedToolset) as e:
        check_init_tools([*ALLOWED_TOOLS, "Bash"])
    assert e.value.extra == ["Bash"] and e.value.missing == []


def test_check_init_tools_rejects_missing() -> None:
    with pytest.raises(UnexpectedToolset) as e:
        check_init_tools(ALLOWED_TOOLS[:3])
    assert e.value.extra == [] and e.value.missing == ALLOWED_TOOLS[3:]


async def test_mcp_tools_delegate_to_agent_tools() -> None:
    tools = RecordingTools()
    handlers = {t.name: t.handler for t in build_sdk_tools(tools)}  # type: ignore[arg-type]
    assert sorted(handlers) == sorted(n.removeprefix("mcp__umowy__") for n in ALLOWED_TOOLS)
    await handlers["read_fragment"]({"fragment_id": "f001"})
    await handlers["submit_finding"](
        {"typ": "kara", "teza": "t", "cytat": "c", "fragment_id": "f001", "uzasadnienie": "u"}
    )
    assert tools.calls == [
        ("read_fragment", {"fragment_id": "f001"}),
        (
            "submit_finding",
            {
                "typ": "kara",
                "teza": "t",
                "cytat": "c",
                "fragment_id": "f001",
                "uzasadnienie": "u",
                "poziom_ryzyka": None,
                "template_id": None,
            },
        ),
    ]


async def test_mcp_tools_closed_until_gate_opens() -> None:
    tools = RecordingTools()
    opened = False
    sdk_tools = build_sdk_tools(tools, gate=lambda: opened)  # type: ignore[arg-type]
    handlers = {t.name: t.handler for t in sdk_tools}
    r = await handlers["list_fragments"]({})
    assert r["is_error"] and tools.calls == []
    opened = True
    await handlers["list_fragments"]({})
    assert tools.calls == [("list_fragments", {})]


def fake_query(messages: list[Message], seen: dict[str, Any]) -> Any:
    async def q(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Message]:
        seen["prompt"] = prompt
        seen["options"] = options
        try:
            for m in messages:
                seen["yielded"] = seen.get("yielded", 0) + 1
                yield m
        finally:
            seen["closed"] = True

    return q


async def test_run_aborts_on_unexpected_toolset() -> None:
    tools = RecordingTools()
    seen: dict[str, Any] = {}
    msgs: list[Message] = [
        _init([*ALLOWED_TOOLS, "WebFetch"]),
        AssistantMessage(content=[TextBlock("x")], model="m"),
        _result("success"),
    ]
    runner = SdkAgentRunner(_settings(), query_fn=fake_query(msgs, seen))
    with structlog.testing.capture_logs() as logs:
        out = await runner.run(CTX, tools)  # type: ignore[arg-type]
    assert out.status == "failed" and out.reason == "niezgodny_zestaw_narzedzi"
    assert tools.calls == []
    assert seen["yielded"] == 1 and seen["closed"]
    mismatch = [e for e in logs if e["event"] == "agent_toolset_mismatch"]
    assert mismatch and mismatch[0]["extra"] == ["WebFetch"] and mismatch[0]["missing"] == []


async def test_run_fails_closed_when_init_has_no_tools_list() -> None:
    msgs: list[Message] = [SystemMessage(subtype="init", data={}), _result("success")]
    runner = SdkAgentRunner(_settings(), query_fn=fake_query(msgs, {}))
    out = await runner.run(CTX, RecordingTools())  # type: ignore[arg-type]
    assert out.reason == "niezgodny_zestaw_narzedzi"


async def test_run_fails_closed_when_result_arrives_before_init() -> None:
    runner = SdkAgentRunner(_settings(), query_fn=fake_query([_result("success")], {}))
    out = await runner.run(CTX, RecordingTools())  # type: ignore[arg-type]
    assert out.reason == "niezgodny_zestaw_narzedzi"


async def test_run_success_passes_prompt_and_maps_result() -> None:
    seen: dict[str, Any] = {}
    msgs: list[Message] = [_init(ALLOWED_TOOLS), _result("error_max_budget_usd", is_error=True)]
    runner = SdkAgentRunner(_settings(), query_fn=fake_query(msgs, seen))
    out = await runner.run(CTX, RecordingTools())  # type: ignore[arg-type]
    assert (out.status, out.reason, out.turns) == ("budget_exceeded", "budget", 4)
    assert seen["prompt"] == start_prompt(CTX)
    assert seen["options"].allowed_tools == ALLOWED_TOOLS
    assert not Path(seen["options"].cwd).exists()  # katalog roboczy sprzątnięty po run


async def test_run_without_result_is_failed() -> None:
    runner = SdkAgentRunner(_settings(), query_fn=fake_query([_init(ALLOWED_TOOLS)], {}))
    out = await runner.run(CTX, RecordingTools())  # type: ignore[arg-type]
    assert (out.status, out.reason) == ("failed", "brak_wyniku")


async def test_run_timeout_is_budget_exceeded() -> None:
    async def slow(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Message]:
        yield _init(ALLOWED_TOOLS)
        await asyncio.sleep(10)

    runner = SdkAgentRunner(_settings(), query_fn=slow, timeout_s=0.05)
    out = await runner.run(CTX, RecordingTools())  # type: ignore[arg-type]
    assert (out.status, out.reason) == ("budget_exceeded", "timeout")


async def test_sdk_error_reason_is_class_name_without_message() -> None:
    async def broken(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[Message]:
        raise CLIConnectionError("tajna treść umowy")
        yield  # pragma: no cover

    runner = SdkAgentRunner(_settings(), query_fn=broken)
    out = await runner.run(CTX, RecordingTools())  # type: ignore[arg-type]
    assert (out.status, out.reason) == ("failed", "CLIConnectionError")
