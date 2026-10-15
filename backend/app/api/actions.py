"""Wnioski o akcje wysokiego ryzyka i decyzje prawnika; pobieranie eksportów."""

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.api.deps import DbDep, SettingsDep, UserDep, current_user, require_role
from app.api.errors import ApiError
from app.domain.model import ActionStatus
from app.repo import actions, analyses, exports
from app.repo.actions import ActionAlreadyDecided
from app.security.sessions import UserRow
from app.services import actions as actions_service
from app.services.actions import (
    ReportNotAvailable,
    TemplateInput,
    TemplateRequired,
    UserActionType,
)

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


ANALYSIS_NOT_FOUND = ApiError(404, "nie_znaleziono_analizy", "Nie znaleziono analizy.")
ACTION_NOT_FOUND = ApiError(404, "nie_znaleziono_wniosku", "Nie znaleziono wniosku.")
REPORT_NOT_AVAILABLE = ApiError(
    409, "raport_niedostepny", "Raport tej analizy nie jest jeszcze dostępny."
)


@router.get("/actions")
def list_actions(db: DbDep, status: ActionStatus | None = None) -> list[ActionOut]:
    rows = actions.list_actions(db, status)
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
def create_action(analysis_id: int, body: ActionIn, db: DbDep, user: UserDep) -> ActionCreated:
    analysis = analyses.get_analysis(db, analysis_id)
    if analysis is None:
        raise ANALYSIS_NOT_FOUND
    try:
        action_id = actions_service.request_user_action(db, analysis, body.typ, user.id)
    except ReportNotAvailable:
        raise REPORT_NOT_AVAILABLE from None
    db.commit()
    return ActionCreated(action_id=action_id)


@router.post("/actions/{action_id}/decision")
def decide_action(
    action_id: int, body: DecisionIn, db: DbDep, lawyer: LawyerDep, settings: SettingsDep
) -> DecisionOut:
    action = actions.get_action(db, action_id)
    if action is None:
        raise ACTION_NOT_FOUND
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
        raise REPORT_NOT_AVAILABLE from None
    db.commit()
    return DecisionOut(id=action_id, status=result.status, export_id=result.export_id)


@router.get("/exports/{export_id}")
def get_export(export_id: int, db: DbDep) -> Response:
    e = exports.get_export(db, export_id)
    if e is None:
        raise ApiError(404, "nie_znaleziono_eksportu", "Nie znaleziono eksportu.")
    return Response(
        content=json.dumps(e.content, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="raport-analizy-{e.analysis_id}.json"'
        },
    )
