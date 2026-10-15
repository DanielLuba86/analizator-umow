# ruff: noqa: F401, F811
import asyncio
from typing import Any, cast

import pytest
from test_tools import QUOTE, Env, conn, env, sf

from app.agent.fake_runner import FakeAgentRunner, ToolCall
from app.agent.guard import BudgetExceeded, LoopGuard
from app.agent.tools import AgentTools

GOOD = ToolCall(
    "submit_finding",
    {
        "typ": "kara",
        "teza": "Kara umowna",
        "cytat": QUOTE,
        "fragment_id": "f003",
        "uzasadnienie": "u",
        "poziom_ryzyka": "wysokie",
    },
)


def runner(script: list[ToolCall], **kw: Any) -> FakeAgentRunner:
    args: dict[str, Any] = {"max_turns": 30, "max_budget_usd": 0.5, "timeout_s": 5.0} | kw
    return FakeAgentRunner(script, **args)


def test_guard_semantics() -> None:
    g = LoopGuard(max_turns=2, max_budget_usd=1.0)
    g.on_turn(0.1)
    g.on_turn(0.1)
    with pytest.raises(BudgetExceeded) as e:
        g.on_turn(0.1)
    assert e.value.kind == "turns"
    assert g.turns == 2 and g.cost_usd == pytest.approx(0.2)


async def test_fake_run_done_with_verified_findings(env: Env) -> None:
    tools = env.tools()
    script = [
        ToolCall("list_fragments", {}),
        ToolCall("read_fragment", {"fragment_id": "f003"}),
        GOOD,
    ]
    out = await runner(script).run(tools.ctx, tools)
    assert (out.status, out.turns, out.reason) == ("done", 3, None)
    assert out.cost_usd == pytest.approx(0.03)
    assert env.count_findings(tools.ctx.analysis_id) == 1


async def test_fake_run_stops_at_max_turns(env: Env) -> None:
    tools = env.tools()
    out = await runner([GOOD] * 40, max_turns=30, max_budget_usd=100).run(tools.ctx, tools)
    assert (out.status, out.reason, out.turns) == ("budget_exceeded", "turns", 30)
    assert env.count_findings(tools.ctx.analysis_id) == 30


async def test_script_of_exactly_max_turns_is_done(env: Env) -> None:
    tools = env.tools()
    out = await runner([GOOD] * 5, max_turns=5).run(tools.ctx, tools)
    assert (out.status, out.turns) == ("done", 5)


async def test_fake_run_stops_at_budget(env: Env) -> None:
    tools = env.tools()
    script = [ToolCall("list_fragments", {}, cost_usd=0.2)] * 10
    out = await runner(script, max_budget_usd=0.5).run(tools.ctx, tools)
    assert (out.status, out.reason, out.turns) == ("budget_exceeded", "budget", 3)
    assert out.cost_usd == pytest.approx(0.6)


async def test_fake_run_timeout() -> None:
    class Slow:
        async def list_fragments(self) -> dict[str, Any]:
            await asyncio.sleep(10)
            return {}

    out = await runner([ToolCall("list_fragments", {})], timeout_s=0.05).run(
        cast(Any, None), cast(AgentTools, Slow())
    )
    assert (out.status, out.reason) == ("budget_exceeded", "timeout")
    assert out.turns == 1


async def test_tool_exception_fails_without_message() -> None:
    class Boom:
        async def list_fragments(self) -> dict[str, Any]:
            raise ValueError("treść umowy tajna")

    out = await runner([ToolCall("list_fragments", {})]).run(
        cast(Any, None), cast(AgentTools, Boom())
    )
    assert (out.status, out.reason) == ("failed", "ValueError")
    assert "tajna" not in repr(out)


async def test_unknown_tool_is_failed(env: Env) -> None:
    tools = env.tools()
    out = await runner([ToolCall("rm_rf", {})]).run(tools.ctx, tools)
    assert out.status == "failed"
