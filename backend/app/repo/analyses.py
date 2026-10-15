from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.model import AnalysisStatus, Claim
from app.domain.quotes import QuoteMatch, RejectReason
from app.repo.models import Analysis, ContractVersion, Finding, RejectedClaim

FindingRow = Finding

ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("done", "failed", "quarantined", "budget_exceeded")


class AnalysisAlreadyActive(Exception):
    """Dla wersji trwa już analiza (queued/running)."""


def active_analysis(s: Session, version_id: int) -> int | None:
    return s.scalar(
        select(Analysis.id)
        .where(Analysis.version_id == version_id, Analysis.status.in_(ACTIVE_STATUSES))
        .order_by(Analysis.id)
        .limit(1)
    )


def create_analysis(s: Session, version_id: int, started_by: int, model: str) -> int:
    s.execute(
        select(ContractVersion.id).where(ContractVersion.id == version_id).with_for_update()
    ).one()
    if active_analysis(s, version_id) is not None:
        raise AnalysisAlreadyActive
    a = Analysis(version_id=version_id, status="queued", model=model, started_by=started_by)
    s.add(a)
    s.flush()
    return a.id


def set_status(
    s: Session,
    analysis_id: int,
    status: AnalysisStatus,
    *,
    turns: int | None = None,
    cost_usd: float | None = None,
    reason: str | None = None,
) -> None:
    a = s.execute(select(Analysis).where(Analysis.id == analysis_id)).scalar_one()
    a.status = status
    if turns is not None:
        a.turns = turns
    if cost_usd is not None:
        a.cost_usd = cost_usd  # type: ignore[assignment]
    if reason is not None:
        a.reason = reason
    if status in TERMINAL_STATUSES:
        a.finished_at = datetime.now(UTC)
    s.flush()


def add_finding(s: Session, analysis_id: int, claim: Claim, match: QuoteMatch) -> int:
    f = Finding(
        analysis_id=analysis_id,
        typ=claim.typ,
        teza=claim.teza,
        cytat=claim.cytat,
        fragment_id=claim.fragment_id,
        start=match.start,
        end=match.end,
        poziom_ryzyka=claim.poziom_ryzyka,
        uzasadnienie=claim.uzasadnienie,
        template_id=claim.template_id,
    )
    s.add(f)
    s.flush()
    return f.id


def add_rejected(s: Session, analysis_id: int, claim: Claim, reason: RejectReason) -> int:
    r = RejectedClaim(
        analysis_id=analysis_id,
        typ=claim.typ,
        teza=claim.teza,
        cytat=claim.cytat,
        fragment_id=claim.fragment_id,
        poziom_ryzyka=claim.poziom_ryzyka,
        uzasadnienie=claim.uzasadnienie,
        template_id=claim.template_id,
        powod=reason,
    )
    s.add(r)
    s.flush()
    return r.id


def count_findings(s: Session, analysis_id: int) -> int:
    return (
        s.scalar(
            select(func.count()).select_from(Finding).where(Finding.analysis_id == analysis_id)
        )
        or 0
    )


def list_findings(s: Session, analysis_id: int) -> list[FindingRow]:
    return list(
        s.scalars(
            select(Finding)
            .where(Finding.analysis_id == analysis_id)
            .order_by(Finding.start, Finding.id)
        )
    )
