"""Strażnik pętli agenta: limity tur i budżetu (timeout egzekwuje runner)."""

from typing import Literal


class BudgetExceeded(Exception):
    def __init__(self, kind: Literal["turns", "budget", "timeout"]) -> None:
        super().__init__(kind)
        self.kind = kind


class LoopGuard:
    def __init__(self, max_turns: int, max_budget_usd: float) -> None:
        self._max_turns = max_turns
        self._max_budget_usd = max_budget_usd
        self._turns = 0
        self._cost_usd = 0.0

    @property
    def turns(self) -> int:
        return self._turns

    @property
    def cost_usd(self) -> float:
        return self._cost_usd

    def on_turn(self, cost_usd: float) -> None:
        """Wołać PRZED wykonaniem wywołania narzędzia."""
        if self._turns >= self._max_turns:
            raise BudgetExceeded("turns")
        self._turns += 1
        self._cost_usd += cost_usd
        if self._cost_usd > self._max_budget_usd:
            raise BudgetExceeded("budget")
