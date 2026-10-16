"""Logowanie: sesja po stronie serwera, w przeglądarce tylko ciasteczko HttpOnly."""

from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import SESSION_COOKIE, DbDep, SettingsDep, UserDep
from app.api.errors import ApiError
from app.repo.audit import audit
from app.repo.users import get_user_by_login
from app.security.passwords import hash_password, verify_password
from app.security.sessions import (
    create_session,
    delete_expired_sessions,
    delete_session,
    resolve_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_PATH = "/api"


def bad_credentials() -> ApiError:
    return ApiError(401, "nieprawidlowe_dane_logowania", "Nieprawidłowy login lub hasło.")


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


class MeOut(BaseModel):
    id: int
    login: str
    role: str


@lru_cache
def _dummy_hash() -> str:
    """Hash do weryfikacji przy nieznanym loginie — wyrównuje czas odpowiedzi."""
    return hash_password("brak-takiego-uzytkownika")


@router.post("/login", status_code=204)
def login(body: LoginIn, response: Response, db: DbDep, settings: SettingsDep) -> None:
    user = get_user_by_login(db, body.login)
    password_ok = verify_password(user.password_hash if user else _dummy_hash(), body.password)
    if user is None or not password_ok:
        audit(db, user.id if user else None, "login_failed", "auth")
        db.commit()
        raise bad_credentials()
    delete_expired_sessions(db, datetime.now(UTC))  # sprzątanie przy okazji logowania
    token = create_session(db, user.id, settings.session_ttl_hours)
    audit(db, user.id, "login", f"user:{user.id}")
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbDep, settings: SettingsDep) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        user = resolve_session(db, token)
        delete_session(db, token)
        if user is not None:
            audit(db, user.id, "logout", f"user:{user.id}")
        db.commit()
    response.delete_cookie(
        SESSION_COOKIE,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.get("/me")
def me(user: UserDep) -> MeOut:
    return MeOut(id=user.id, login=user.login, role=user.role)
