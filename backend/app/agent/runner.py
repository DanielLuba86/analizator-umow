from dataclasses import dataclass
from typing import Literal, Protocol

from app.agent.context import AnalysisContext
from app.agent.tools import AgentTools


@dataclass(frozen=True)
class RunOutcome:
    status: Literal["done", "budget_exceeded", "failed"]
    turns: int
    cost_usd: float
    reason: str | None = None


class AgentRunner(Protocol):
    async def run(self, ctx: AnalysisContext, tools: AgentTools) -> RunOutcome: ...
