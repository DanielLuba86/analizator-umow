from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repo.models import Export

ExportRow = Export


def add_export(s: Session, analysis_id: int, action_id: int, content: dict[str, Any]) -> int:
    e = Export(analysis_id=analysis_id, action_id=action_id, content=content)
    s.add(e)
    s.flush()
    return e.id


def get_export(s: Session, export_id: int) -> ExportRow | None:
    return s.get(Export, export_id)


def export_ids_by_action(s: Session, action_ids: Sequence[int]) -> dict[int, int]:
    if not action_ids:
        return {}
    rows = s.execute(select(Export.action_id, Export.id).where(Export.action_id.in_(action_ids)))
    return {action_id: export_id for action_id, export_id in rows}
