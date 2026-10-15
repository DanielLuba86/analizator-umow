import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.repo.models import Session as SessionRow
from app.repo.models import User

UserRow = User


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(s: Session, user_id: int, ttl_hours: int) -> str:
    token = secrets.token_urlsafe(32)
    s.add(
        SessionRow(
            token_hash=_hash(token),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )
    )
    s.flush()
    return token


def resolve_session(s: Session, token: str) -> UserRow | None:
    row = s.get(SessionRow, _hash(token))
    if row is None:
        return None
    if row.expires_at <= datetime.now(UTC):
        s.delete(row)
        s.flush()
        return None
    return s.get(UserRow, row.user_id)


def delete_session(s: Session, token: str) -> None:
    row = s.get(SessionRow, _hash(token))
    if row is not None:
        s.delete(row)
        s.flush()
