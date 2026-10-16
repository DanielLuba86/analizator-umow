"""Wnioski o akcje wysokiego ryzyka i decyzje prawnika; pobieranie eksportów."""

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.api.deps import DbDep, SettingsDep, UserDep, current_user, require_role
from app.api.errors import ApiError
from app.domain.model import ActionStatus
from app.repo import actions, analyses, exports, users
from app.repo.actions import ActionAlreadyDecided
from app.security.sessions import UserRow
from app.services import actions as actions_service
from app.services.actions import (
    ReportNotAvailable,
    TemplateInput,
    TemplateRequired,
    UserActionType,
)
from app.services.pdf_report import render_report

router = APIRouter(prefix="/api", tags=["actions"], dependencies=[Depends(current_user)])

LawyerDep = Annotated[UserRow, Depends(require_role("prawnik"))]
ClauseName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ClauseText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)
]


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    typ: UserActionType


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nazwa_klauzuli: ClauseName
    tresc: ClauseText


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    template: TemplateIn | None = None


class ActionCreated(BaseModel):
    action_id: int


class ActionOut(BaseModel):
    id: int
    typ: str
    analysis_id: int
    status: str
    payload: dict[str, Any]
    created_at: datetime
    decided_by: int | None
    decided_at: datetime | None
    export_id: int | None


class DecisionOut(BaseModel):
    id: int
    status: str
    export_id: int | None


def analysis_not_found() -> ApiError:
    return ApiError(404, "nie_znaleziono_analizy", "Nie znaleziono analizy.")


def action_not_found() -> ApiError:
    return ApiError(404, "nie_znaleziono_wniosku", "Nie znaleziono wniosku.")


def report_not_available() -> ApiError:
    return ApiError(409, "raport_niedostepny", "Raport tej analizy nie jest jeszcze dostępny.")


@router.get("/actions")
def list_actions(
    db: DbDep, status: ActionStatus | None = None, analysis_id: int | None = None
) -> list[ActionOut]:
    rows = actions.list_actions(db, status, analysis_id)
    export_ids = exports.export_ids_by_action(db, [a.id for a in rows])
    visible: dict[int, bool] = {}
    return [
        ActionOut(
            id=a.id,
            typ=a.typ,
            analysis_id=a.analysis_id,
            status=a.status,
            payload=actions_service.public_payload(db, a, visible),
            created_at=a.created_at,
            decided_by=a.decided_by,
            decided_at=a.decided_at,
            export_id=export_ids.get(a.id),
        )
        for a in rows
    ]


@router.post("/analyses/{analysis_id}/actions", status_code=201)
def create_action(
    analysis_id: int, body: ActionIn, db: DbDep, user: UserDep, response: Response
) -> ActionCreated:
    """201 — nowy wniosek; 200 — ten sam oczekujący wniosek już istnieje."""
    analysis = analyses.get_analysis(db, analysis_id)
    if analysis is None:
        raise analysis_not_found()
    try:
        requested = actions_service.request_user_action(db, analysis, body.typ, user.id)
    except ReportNotAvailable:
        raise report_not_available() from None
    db.commit()
    if not requested.created:
        response.status_code = 200
    return ActionCreated(action_id=requested.id)


@router.post("/actions/{action_id}/decision")
def decide_action(
    action_id: int, body: DecisionIn, db: DbDep, lawyer: LawyerDep, settings: SettingsDep
) -> DecisionOut:
    action = actions.get_action(db, action_id)
    if action is None:
        raise action_not_found()
    if body.template is not None and not (body.approve and action.typ == "wzorzec"):
        raise ApiError(
            422, "wzorzec_niedozwolony", "Treść wzorca podaje się tylko przy zatwierdzaniu wzorca."
        )
    template = (
        None
        if body.template is None
        else TemplateInput(body.template.nazwa_klauzuli, body.template.tresc)
    )
    try:
        result = actions_service.decide(
            db,
            action,
            decided_by=lawyer.id,
            approve=body.approve,
            settings=settings,
            template=template,
        )
    except ActionAlreadyDecided:
        db.rollback()
        raise ApiError(
            409, "wniosek_rozstrzygniety", "Wniosek został już rozstrzygnięty."
        ) from None
    except TemplateRequired:
        db.rollback()
        raise ApiError(
            422, "brak_tresci_wzorca", "Zatwierdzenie wzorca wymaga nazwy i treści klauzuli."
        ) from None
    except ReportNotAvailable:
        db.rollback()
        raise report_not_available() from None
    db.commit()
    return DecisionOut(id=action_id, status=result.status, export_id=result.export_id)


def _export_or_404(db: DbDep, export_id: int) -> exports.ExportRow:
    e = exports.get_export(db, export_id)
    if e is None:
        raise ApiError(404, "nie_znaleziono_eksportu", "Nie znaleziono eksportu.")
    return e


def _download(content: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/exports/{export_id}")
def get_export(export_id: int, db: DbDep) -> Response:
    e = _export_or_404(db, export_id)
    return _download(
        json.dumps(e.content, ensure_ascii=False, indent=2),
        "application/json",
        f"raport-analizy-{e.analysis_id}.json",
    )


@router.get("/exports/{export_id}/pdf")
def get_export_pdf(export_id: int, db: DbDep, settings: SettingsDep) -> Response:
    """Raport dla klienta z tej samej zamrożonej treści co JSON (bez osobnego wniosku)."""
    e = _export_or_404(db, export_id)
    approver = users.get_login(db, e.content["approved_by"])
    pdf = render_report(e.content, approver=approver, firm_name=settings.report_firm_name)
    return _download(pdf, "application/pdf", f"raport-analizy-{e.analysis_id}.pdf")
