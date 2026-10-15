from sqlalchemy.orm import Session

from app.repo.models import AuditLog


def audit(s: Session, user_id: int | None, action: str, obj: str) -> None:
    s.add(AuditLog(user_id=user_id, akcja=action, obiekt=obj))
    s.flush()
