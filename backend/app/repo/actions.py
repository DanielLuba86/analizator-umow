from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.model import ActionType
from app.repo.models import PendingAction

ActionRow = PendingAction


class ActionAlreadyDecided(Exception):
    """Wniosek został już rozstrzygnięty."""


def request_action(s: Session, analysis_id: int, typ: ActionType, payload: dict[str, Any]) -> int:
    existing = s.scalar(
        select(PendingAction.id).where(
            PendingAction.analysis_id == analysis_id,
            PendingAction.typ == typ,
            PendingAction.status == "oczekuje",
        )
    )
    if existing is not None:
        return existing
    a = PendingAction(typ=typ, analysis_id=analysis_id, payload=payload, status="oczekuje")
    s.add(a)
    s.flush()
    return a.id


def decide_action(s: Session, action_id: int, decided_by: int, approve: bool) -> ActionRow:
    a = s.execute(
        select(PendingAction)
        .where(PendingAction.id == action_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if a.status != "oczekuje":
        raise ActionAlreadyDecided
    a.status = "zatwierdzona" if approve else "odrzucona"
    a.decided_by = decided_by
    a.decided_at = datetime.now(UTC)
    s.flush()
    return a


def list_pending(s: Session) -> list[ActionRow]:
    return list(
        s.scalars(
            select(PendingAction)
            .where(PendingAction.status == "oczekuje")
            .order_by(PendingAction.id)
        )
    )


def latest_action(s: Session, analysis_id: int, typ: ActionType) -> ActionRow | None:
    """Najnowszy wniosek danego typu dla analizy (dowolny status)."""
    return s.scalar(
        select(PendingAction)
        .where(PendingAction.analysis_id == analysis_id, PendingAction.typ == typ)
        .order_by(PendingAction.id.desc())
        .limit(1)
    )
