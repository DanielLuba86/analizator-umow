"""Wspólny model dziedziny: typy tez, statusy i walidacja tezy agenta."""

from dataclasses import dataclass
from typing import Literal, get_args

FindingType = Literal["strona", "termin", "kara", "ryzyko", "wstrzyknięcie"]
RiskLevel = Literal["niskie", "średnie", "wysokie"]
ActionType = Literal["opinia", "wzorzec", "eksport", "kwarantanna"]
ActionStatus = Literal["oczekuje", "zatwierdzona", "odrzucona"]
AnalysisStatus = Literal["queued", "running", "done", "failed", "quarantined", "budget_exceeded"]

FINDING_TYPES: tuple[FindingType, ...] = get_args(FindingType)
RISK_LEVELS: tuple[RiskLevel, ...] = get_args(RiskLevel)
ACTION_TYPES: tuple[ActionType, ...] = get_args(ActionType)
ACTION_STATUSES: tuple[ActionStatus, ...] = get_args(ActionStatus)
ANALYSIS_STATUSES: tuple[AnalysisStatus, ...] = get_args(AnalysisStatus)

MAX_TEZA_LEN = 500


@dataclass(frozen=True)
class Claim:
    typ: FindingType
    teza: str
    cytat: str
    fragment_id: str
    uzasadnienie: str
    poziom_ryzyka: RiskLevel | None = None
    template_id: int | None = None


class ClaimInvalid(Exception):
    """Teza narusza reguły; `reason` to krótki opis (nigdy treść tezy)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_claim(c: Claim) -> None:
    """Sprawdza reguły tezy; nie weryfikuje cytatu (to robi `verify_quote`)."""
    if c.typ not in FINDING_TYPES:
        raise ClaimInvalid("Nieznany typ tezy.")
    if c.poziom_ryzyka is not None and c.poziom_ryzyka not in RISK_LEVELS:
        raise ClaimInvalid("Nieznany poziom ryzyka.")
    if not c.teza.strip():
        raise ClaimInvalid("Teza nie może być pusta.")
    if len(c.teza) > MAX_TEZA_LEN:
        raise ClaimInvalid(f"Teza jest dłuższa niż {MAX_TEZA_LEN} znaków.")
    if not c.uzasadnienie.strip():
        raise ClaimInvalid("Uzasadnienie nie może być puste.")
    if c.typ == "ryzyko" and c.poziom_ryzyka is None:
        raise ClaimInvalid("Teza typu ryzyko wymaga poziomu ryzyka.")
    if c.poziom_ryzyka is not None and c.typ not in ("ryzyko", "kara"):
        raise ClaimInvalid("Poziom ryzyka jest dozwolony tylko dla typów ryzyko i kara.")
