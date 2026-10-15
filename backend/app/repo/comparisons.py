from typing import Any

from sqlalchemy.orm import Session

from app.repo.models import Comparison


def add_comparison(
    s: Session,
    version_a: int,
    version_b: int,
    fragment_changes: list[dict[str, Any]],
    finding_changes: dict[str, Any] | None,
) -> int:
    c = Comparison(
        version_a=version_a,
        version_b=version_b,
        fragment_changes=fragment_changes,
        finding_changes=finding_changes,
    )
    s.add(c)
    s.flush()
    return c.id
