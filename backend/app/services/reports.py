"""Widoczność raportu analizy — jedna reguła dla API raportu, wniosków i eksportu."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repo import actions
from app.repo.analyses import FindingRow, list_findings
from app.repo.models import Analysis

REPORT_VISIBLE_STATUSES = ("done", "budget_exceeded", "failed")
INCOMPLETE_STATUSES = ("budget_exceeded", "failed")


@dataclass(frozen=True)
class QuarantineState:
    action_id: int
    status: str


def quarantine_state(s: Session, analysis_id: int) -> QuarantineState | None:
    action = actions.latest_action(s, analysis_id, "kwarantanna")
    return None if action is None else QuarantineState(action.id, action.status)


def is_report_visible(s: Session, analysis: Analysis) -> bool:
    """Tezy widać po zakończeniu analizy; w kwarantannie dopiero po zatwierdzeniu wniosku."""
    q = quarantine_state(s, analysis.id)
    approved = q is not None and q.status == "zatwierdzona"
    if analysis.status == "quarantined":
        return approved
    if analysis.status not in REPORT_VISIBLE_STATUSES:
        return False
    # obrona w głąb: wniosek kwarantanny lub wykryte wstrzyknięcie bez zatwierdzenia ukrywa raport
    # niezależnie od statusu (np. failed po błędzie w trakcie analizy)
    if q is not None and not approved:
        return False
    return approved or not any(f.typ == "wstrzyknięcie" for f in list_findings(s, analysis.id))


def visible_findings(s: Session, analysis: Analysis) -> list[FindingRow]:
    return list_findings(s, analysis.id) if is_report_visible(s, analysis) else []
