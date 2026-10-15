"""Analizy (uruchomienie w tle, raport) i porównania wersji.

Raport pokazuje tezy tylko dla analiz zakończonych i nie w kwarantannie — albo w kwarantannie
z zatwierdzonym wnioskiem `kwarantanna`. Tezy odrzucone (`rejected_claims`) nigdy nie trafiają
do odpowiedzi.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from app.agent.classifier import AnthropicClassifier, InjectionClassifier
from app.agent.runner import AgentRunner
from app.agent.sdk_runner import SdkAgentRunner
from app.api.deps import DbDep, SettingsDep, UserDep, current_user, get_session_factory
from app.api.errors import ApiError
from app.repo import analyses, contracts
from app.repo.analyses import AnalysisAlreadyActive, FindingRow
from app.repo.audit import audit
from app.services.analysis import run_analysis
from app.services.comparison import VersionsOfDifferentContracts, compare_versions
from app.services.reports import INCOMPLETE_STATUSES, quarantine_state, visible_findings

router = APIRouter(prefix="/api", tags=["analyses"], dependencies=[Depends(current_user)])


def get_runner(settings: SettingsDep) -> AgentRunner:
    return SdkAgentRunner(settings)


def get_classifier(settings: SettingsDep) -> InjectionClassifier:
    return AnthropicClassifier(settings)


class AnalysisStarted(BaseModel):
    analysis_id: int


class FindingOut(BaseModel):
    id: int
    typ: str
    teza: str
    cytat: str
    fragment_id: str
    start: int
    end: int
    poziom_ryzyka: str | None
    uzasadnienie: str
    template_id: int | None


def finding_out(f: FindingRow) -> FindingOut:
    return FindingOut(
        id=f.id,
        typ=f.typ,
        teza=f.teza,
        cytat=f.cytat,
        fragment_id=f.fragment_id,
        start=f.start,
        end=f.end,
        poziom_ryzyka=f.poziom_ryzyka,
        uzasadnienie=f.uzasadnienie,
        template_id=f.template_id,
    )


class QuarantineOut(BaseModel):
    action_id: int
    status: str


class AnalysisReport(BaseModel):
    id: int
    version_id: int
    status: str
    reason: str | None
    turns: int | None
    cost_usd: float | None
    incomplete: bool
    official: bool
    quarantine: QuarantineOut | None
    findings: list[FindingOut]


class ComparisonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_a: int
    version_b: int


class ComparisonOut(BaseModel):
    id: int
    fragment_changes: list[dict[str, Any]]
    finding_changes: dict[str, list[dict[str, str]]] | None


VERSION_NOT_FOUND = ApiError(404, "nie_znaleziono_wersji", "Nie znaleziono wersji umowy.")
ANALYSIS_NOT_FOUND = ApiError(404, "nie_znaleziono_analizy", "Nie znaleziono analizy.")


@router.post("/versions/{version_id}/analyses", status_code=202)
def start_analysis(
    version_id: int,
    background: BackgroundTasks,
    db: DbDep,
    user: UserDep,
    settings: SettingsDep,
    sf: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    runner: Annotated[AgentRunner, Depends(get_runner)],
    classifier: Annotated[InjectionClassifier, Depends(get_classifier)],
) -> AnalysisStarted:
    if contracts.find_version(db, version_id) is None:
        raise VERSION_NOT_FOUND
    try:
        aid = analyses.create_analysis(db, version_id, user.id, settings.agent_model)
    except AnalysisAlreadyActive:
        db.rollback()
        raise ApiError(409, "analiza_w_toku", "Dla tej wersji trwa już analiza.") from None
    audit(db, user.id, "analysis_start", f"analysis:{aid}")
    db.commit()
    background.add_task(
        run_analysis,
        aid,
        session_factory=sf,
        runner=runner,
        classifier=classifier,
        settings=settings,
    )
    return AnalysisStarted(analysis_id=aid)


@router.get("/analyses/{analysis_id}")
def get_report(analysis_id: int, db: DbDep) -> AnalysisReport:
    a = analyses.get_analysis(db, analysis_id)
    if a is None:
        raise ANALYSIS_NOT_FOUND
    q = quarantine_state(db, analysis_id)
    quarantine = None if q is None else QuarantineOut(action_id=q.action_id, status=q.status)
    findings = [finding_out(f) for f in visible_findings(db, a)]
    return AnalysisReport(
        id=a.id,
        version_id=a.version_id,
        status=a.status,
        reason=a.reason,
        turns=a.turns,
        cost_usd=float(a.cost_usd) if a.cost_usd is not None else None,
        incomplete=a.status in INCOMPLETE_STATUSES,
        official=a.official,
        quarantine=quarantine,
        findings=findings,
    )


@router.post("/comparisons", status_code=201)
def create_comparison(body: ComparisonIn, db: DbDep, user: UserDep) -> ComparisonOut:
    for vid in (body.version_a, body.version_b):
        if contracts.find_version(db, vid) is None:
            raise VERSION_NOT_FOUND
    try:
        result = compare_versions(db, body.version_a, body.version_b)
    except VersionsOfDifferentContracts:
        raise ApiError(422, "rozne_umowy", "Porównywane wersje należą do różnych umów.") from None
    audit(db, user.id, "comparison_create", f"comparison:{result.id}")
    db.commit()
    return ComparisonOut(
        id=result.id,
        fragment_changes=result.fragment_changes,
        finding_changes=result.finding_changes,
    )
