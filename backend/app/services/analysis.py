"""Orkiestrator analizy: detektor wstrzyknięć (heurystyki + klasyfikator), agent, status końcowy.

Agent działa niezależnie od wyniku detekcji (jest izolowany); trafienie detektora, teza agenta
typu ``wstrzyknięcie`` albo niedostępny klasyfikator kończą analizę kwarantanną. Logi zawierają
wyłącznie identyfikatory, liczniki i nazwy klas wyjątków — nigdy treść umowy.
"""

from collections.abc import Sequence
from typing import Literal

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.agent.classifier import ClassifierUnavailable, InjectionClassifier
from app.agent.context import AnalysisContext
from app.agent.runner import AgentRunner, RunOutcome
from app.agent.tools import AgentTools
from app.config import Settings
from app.domain.fragments import MAX_FRAGMENT_ID_LEN, Fragment, fragment_text
from app.domain.injection import scan_heuristics
from app.domain.model import Claim
from app.domain.quotes import QuoteNotFound, verify_quote
from app.repo import actions, analyses, contracts

log = structlog.get_logger(__name__)

INJECTION_TEZA = "Możliwa ukryta instrukcja dla systemu AI w treści umowy."
CLASSIFIER_DEFAULT_REASON = "klasyfikator"

QuarantineReason = Literal["wstrzyknięcie", "klasyfikator_niedostępny"]


def _store_hit(
    s: Session,
    analysis_id: int,
    text: str,
    frags: Sequence[Fragment],
    fragment_id: str,
    quote: str,
    uzasadnienie: str,
) -> bool:
    """Zapisuje trafienie detektora jako tezę `wstrzyknięcie` po weryfikacji cytatu."""
    claim = Claim(
        typ="wstrzyknięcie",
        teza=INJECTION_TEZA,
        cytat=quote,
        fragment_id=fragment_id[:MAX_FRAGMENT_ID_LEN],
        uzasadnienie=uzasadnienie.strip() or CLASSIFIER_DEFAULT_REASON,
        poziom_ryzyka=None,
        template_id=None,
    )
    try:
        match = verify_quote(text, frags, fragment_id, quote)
    except QuoteNotFound as e:
        analyses.add_rejected(s, analysis_id, claim, e.reason)
        return False
    analyses.add_finding(s, analysis_id, claim, match)
    return True


async def _detect(
    analysis_id: int,
    version_id: int,
    session_factory: sessionmaker[Session],
    classifier: InjectionClassifier,
) -> tuple[int, bool]:
    """Zwraca (liczba przyjętych trafień, czy klasyfikator był niedostępny)."""
    with session_factory() as s:
        text = contracts.get_version_text(s, version_id)
        frags = contracts.list_fragments(s, version_id)
    unavailable = False
    try:
        classifier_hits = await classifier.classify([(f, fragment_text(text, f)) for f in frags])
    except ClassifierUnavailable:
        unavailable, classifier_hits = True, []
    except Exception as e:  # noqa: BLE001 - fail-closed: każdy błąd klasyfikatora = niedostępny
        log.warning("classifier_error", analysis_id=analysis_id, error=type(e).__name__)
        unavailable, classifier_hits = True, []
    accepted = rejected = 0
    with session_factory() as s:
        for h in scan_heuristics(text, frags):
            ok = _store_hit(s, analysis_id, text, frags, h.fragment_id, h.quote, h.rule)
            accepted, rejected = accepted + ok, rejected + (not ok)
        for c in classifier_hits:
            ok = _store_hit(s, analysis_id, text, frags, c.fragment_id, c.quote, c.explanation)
            accepted, rejected = accepted + ok, rejected + (not ok)
        s.commit()
    log.info(
        "injection_detection",
        analysis_id=analysis_id,
        accepted=accepted,
        rejected=rejected,
        classifier_unavailable=unavailable,
    )
    return accepted, unavailable


def _finalize(
    s: Session,
    analysis_id: int,
    classifier_unavailable: bool,
    outcome: RunOutcome | None,
    error: str | None,
) -> QuarantineReason | None:
    """Status końcowy; kwarantanna ma pierwszeństwo także po błędzie przebiegu."""
    injected = any(f.typ == "wstrzyknięcie" for f in analyses.list_findings(s, analysis_id))
    quarantine: QuarantineReason | None = (
        "wstrzyknięcie"
        if injected
        else "klasyfikator_niedostępny"
        if classifier_unavailable
        else None
    )
    turns = outcome.turns if outcome else None
    cost = outcome.cost_usd if outcome else None
    if quarantine is not None:
        actions.request_action(s, analysis_id, "kwarantanna", {"powód": quarantine})
        analyses.set_status(
            s, analysis_id, "quarantined", turns=turns, cost_usd=cost, reason=quarantine
        )
    elif outcome is not None:
        analyses.set_status(
            s, analysis_id, outcome.status, turns=turns, cost_usd=cost, reason=outcome.reason
        )
    else:
        analyses.set_status(s, analysis_id, "failed", reason=error)
    return quarantine


async def run_analysis(
    analysis_id: int,
    *,
    session_factory: sessionmaker[Session],
    runner: AgentRunner,
    classifier: InjectionClassifier,
    settings: Settings,
) -> None:
    classifier_unavailable = False
    try:
        with session_factory() as s:
            version_id, kind = analyses.analysis_target(s, analysis_id)
            analyses.set_status(s, analysis_id, "running")
            s.commit()
        ctx = AnalysisContext(analysis_id, version_id, kind, settings.agent_max_findings)

        _, classifier_unavailable = await _detect(
            analysis_id, version_id, session_factory, classifier
        )
        outcome = await runner.run(ctx, AgentTools(ctx, session_factory))

        with session_factory() as s:
            quarantine = _finalize(s, analysis_id, classifier_unavailable, outcome, None)
            s.commit()
        log.info(
            "analysis_finished",
            analysis_id=analysis_id,
            status="quarantined" if quarantine else outcome.status,
            agent_status=outcome.status,
            agent_reason=outcome.reason,
            turns=outcome.turns,
            cost_usd=outcome.cost_usd,
        )
    except Exception as e:  # noqa: BLE001 - powód to tylko nazwa klasy, nigdy treść
        log.error("analysis_failed", analysis_id=analysis_id, error=type(e).__name__)
        try:
            with session_factory() as s:
                _finalize(s, analysis_id, classifier_unavailable, None, type(e).__name__)
                s.commit()
        except Exception as e2:  # noqa: BLE001
            log.error(
                "analysis_status_update_failed", analysis_id=analysis_id, error=type(e2).__name__
            )
