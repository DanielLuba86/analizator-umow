"""Wnioski o akcje wysokiego ryzyka: tworzenie przez użytkownika, decyzja prawnika, skutek.

Skutek (`execute_approved`) wykonuje się wyłącznie po zatwierdzeniu, w tej samej transakcji
co decyzja i wpis audytu — wycofanie transakcji cofa wszystko naraz.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.repo import actions, analyses, contracts, exports
from app.repo.actions import ActionRow
from app.repo.audit import audit
from app.repo.models import Analysis
from app.repo.templates import add_template_version
from app.services.reports import INCOMPLETE_STATUSES, is_report_visible

UserActionType = Literal["eksport", "opinia"]


class ReportNotAvailable(Exception):
    """Raport analizy jest niewidoczny (w toku lub w kwarantannie bez zatwierdzenia)."""


class TemplateRequired(Exception):
    """Zatwierdzenie wniosku `wzorzec` wymaga nazwy i treści klauzuli od prawnika."""


@dataclass(frozen=True)
class TemplateInput:
    nazwa_klauzuli: str
    tresc: str


@dataclass(frozen=True)
class DecisionResult:
    status: str
    export_id: int | None


def request_user_action(s: Session, analysis: Analysis, typ: UserActionType, user_id: int) -> int:
    """Idempotentnie: istniejący oczekujący wniosek tego typu jest zwracany zamiast nowego."""
    if not is_report_visible(s, analysis):
        raise ReportNotAvailable
    payload = {"zrodlo": "uzytkownik", "user_id": user_id}
    try:
        with s.begin_nested():
            action_id = actions.request_action(s, analysis.id, typ, payload)
    except IntegrityError:  # równoległe żądanie wygrało wyścig o unikat (analiza, typ, oczekuje)
        action_id = actions.request_action(s, analysis.id, typ, payload)
    audit(s, user_id, f"wniosek:{typ}", f"action:{action_id}")
    return action_id


def export_content(s: Session, analysis: Analysis, approved_by: int) -> dict[str, Any]:
    version = contracts.get_version(s, analysis.version_id)
    contract = contracts.get_contract(s, version.contract_id)
    assert contract is not None  # noqa: S101 - FK gwarantuje istnienie
    return {
        "analysis_id": analysis.id,
        "version_id": version.id,
        "version_nr": version.nr,
        "contract": {"id": contract.id, "title": contract.title, "kind": contract.kind},
        "status": analysis.status,
        "official": analysis.official,
        "incomplete": analysis.status in INCOMPLETE_STATUSES,
        "approved_by": approved_by,
        "generated_at": datetime.now(UTC).isoformat(),
        "findings": [
            {
                "typ": f.typ,
                "teza": f.teza,
                "cytat": f.cytat,
                "fragment_id": f.fragment_id,
                "start": f.start,
                "end": f.end,
                "poziom_ryzyka": f.poziom_ryzyka,
                "uzasadnienie": f.uzasadnienie,
            }
            for f in analyses.list_findings(s, analysis.id)
        ],
    }


def execute_approved(
    s: Session,
    action: ActionRow,
    settings: Settings,
    *,
    decided_by: int,
    template: TemplateInput | None = None,
) -> int | None:
    """Wykonuje skutek zatwierdzonego wniosku; zwraca id eksportu dla `eksport`."""
    del settings  # interfejs z planu; skutki nie zależą dziś od ustawień
    analysis = analyses.get_analysis(s, action.analysis_id)
    assert analysis is not None  # noqa: S101 - FK gwarantuje istnienie
    if action.typ == "opinia":
        if not is_report_visible(s, analysis):
            raise ReportNotAvailable
        analyses.mark_official(s, analysis.id)
    elif action.typ == "wzorzec":
        if template is None:
            raise TemplateRequired
        _, kind = analyses.analysis_target(s, analysis.id)
        add_template_version(s, kind, template.nazwa_klauzuli, template.tresc)
    elif action.typ == "eksport":
        if not is_report_visible(s, analysis):
            raise ReportNotAvailable
        return exports.add_export(
            s, analysis.id, action.id, export_content(s, analysis, decided_by)
        )
    elif action.typ == "kwarantanna" and analysis.status == "quarantined":
        analyses.set_status(s, analysis.id, "done")
    return None


def decide(
    s: Session,
    action: ActionRow,
    *,
    decided_by: int,
    approve: bool,
    settings: Settings,
    template: TemplateInput | None = None,
) -> DecisionResult:
    """Rozstrzyga wniosek (blokada wiersza; ponowna decyzja → ActionAlreadyDecided)."""
    if approve and action.typ == "wzorzec" and template is None:
        raise TemplateRequired
    decided = actions.decide_action(s, action.id, decided_by, approve)
    export_id = (
        execute_approved(s, decided, settings, decided_by=decided_by, template=template)
        if approve
        else None
    )
    audit(s, decided_by, f"decyzja:{decided.typ}:{str(approve).lower()}", f"action:{decided.id}")
    return DecisionResult(decided.status, export_id)
