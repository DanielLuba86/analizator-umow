"""Skryptowy runner do testów CI (bez dostępu do Claude API). Wywołania są sekwencyjne."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.agent.context import AnalysisContext
from app.agent.guard import BudgetExceeded, LoopGuard
from app.agent.runner import RunOutcome
from app.agent.tools import AgentTools

TOOL_NAMES = (
    "list_fragments",
    "read_fragment",
    "search_templates",
    "submit_finding",
    "request_action",
)


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.01


class FakeAgentRunner:
    def __init__(
        self,
        script: Sequence[ToolCall],
        max_turns: int,
        max_budget_usd: float,
        timeout_s: float,
    ) -> None:
        self._script = tuple(script)
        self._max_turns = max_turns
        self._max_budget_usd = max_budget_usd
        self._timeout_s = timeout_s

    async def _play(self, tools: AgentTools, guard: LoopGuard) -> None:
        for call in self._script:
            guard.on_turn(call.cost_usd)
            if call.name not in TOOL_NAMES:
                raise LookupError("unknown tool in script")
            await getattr(tools, call.name)(**call.args)

    async def run(self, ctx: AnalysisContext, tools: AgentTools) -> RunOutcome:
        guard = LoopGuard(self._max_turns, self._max_budget_usd)
        try:
            await asyncio.wait_for(self._play(tools, guard), timeout=self._timeout_s)
        except TimeoutError:
            return RunOutcome("budget_exceeded", guard.turns, guard.cost_usd, "timeout")
        except BudgetExceeded as e:
            return RunOutcome("budget_exceeded", guard.turns, guard.cost_usd, e.kind)
        except Exception as e:  # noqa: BLE001 - powód to tylko nazwa klasy, nigdy treść
            return RunOutcome("failed", guard.turns, guard.cost_usd, type(e).__name__)
        return RunOutcome("done", guard.turns, guard.cost_usd, None)
