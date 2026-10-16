import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repo.models import Session as SessionRow
from app.repo.models import User
from app.security.sessions import (
    create_session,
    delete_expired_sessions,
    delete_session,
    resolve_session,
)


def _user(s: Session) -> int:
    u = User(login="sess-user", password_hash="x", role="prawnik")  # noqa: S106
    s.add(u)
    s.flush()
    return u.id


def test_session_token_not_stored_in_plaintext(db_session: Session) -> None:
    uid = _user(db_session)
    token = create_session(db_session, uid, 8)
    hashes = list(db_session.scalars(select(SessionRow.token_hash)))
    assert token not in hashes
    assert hashlib.sha256(token.encode()).hexdigest() in hashes
    user = resolve_session(db_session, token)
    assert user is not None and user.id == uid


def test_expired_session_rejected(db_session: Session) -> None:
    uid = _user(db_session)
    token = create_session(db_session, uid, 8)
    row = db_session.get(SessionRow, hashlib.sha256(token.encode()).hexdigest())
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()
    assert resolve_session(db_session, token) is None
    assert db_session.get(SessionRow, row.token_hash) is None


def test_resolve_unknown_token_returns_none(db_session: Session) -> None:
    assert resolve_session(db_session, "nie-istnieje") is None


def test_delete_session(db_session: Session) -> None:
    uid = _user(db_session)
    token = create_session(db_session, uid, 8)
    delete_session(db_session, token)
    assert resolve_session(db_session, token) is None
    delete_session(db_session, token)  # brak błędu przy ponownym usunięciu


def test_delete_expired_sessions_keeps_live(db_session: Session) -> None:
    uid = _user(db_session)
    live = create_session(db_session, uid, 8)
    now = datetime.now(UTC)
    db_session.add(SessionRow(token_hash="e" * 64, user_id=uid, expires_at=now - timedelta(1)))
    db_session.flush()
    assert delete_expired_sessions(db_session, now) == 1
    hashes = list(db_session.scalars(select(SessionRow.token_hash)))
    assert hashes == [hashlib.sha256(live.encode()).hexdigest()]
