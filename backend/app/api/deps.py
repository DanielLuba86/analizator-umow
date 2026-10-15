"""Zależności API: ustawienia, sesja bazy, zalogowany użytkownik, wymagana rola."""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.api.errors import ApiError
from app.config import Settings, get_settings
from app.domain.model import Role
from app.repo.db import make_engine, session_factory
from app.security.sessions import UserRow, resolve_session

SESSION_COOKIE = "sid"


def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_session_factory(request: Request, settings: SettingsDep) -> sessionmaker[Session]:
    """Silnik tworzony leniwie przy pierwszym żądaniu i trzymany w stanie aplikacji."""
    sf: sessionmaker[Session] | None = getattr(request.app.state, "session_factory", None)
    if sf is None:
        engine = make_engine(settings.database_url)
        request.app.state.engine = engine
        sf = request.app.state.session_factory = session_factory(engine)
    return sf


def get_db(
    sf: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> Iterator[Session]:
    with sf() as s:
        yield s


DbDep = Annotated[Session, Depends(get_db)]

UNAUTHORIZED = ApiError(401, "brak_logowania", "Wymagane zalogowanie.")


def current_user(request: Request, db: DbDep) -> UserRow:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise UNAUTHORIZED
    user = resolve_session(db, token)
    db.commit()  # resolve_session usuwa wygasłe sesje
    if user is None:
        raise UNAUTHORIZED
    return user


UserDep = Annotated[UserRow, Depends(current_user)]


def require_role(role: Role) -> Callable[[UserRow], UserRow]:
    def dependency(user: UserDep) -> UserRow:
        if user.role != role:
            raise ApiError(403, "brak_uprawnien", "Brak uprawnień.")
        return user

    return dependency
