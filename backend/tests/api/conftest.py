"""Fixture'y API: aplikacja na transakcji testowej (wycofywanej), klient zalogowany rolą."""

from collections.abc import Callable, Iterator

import pytest
from api_helpers import PASSWORD, ApiClientFactory, make_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_app_settings, get_session_factory
from app.config import Settings
from app.main import create_app
from app.repo import models
from app.security.passwords import hash_password


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(sf: sessionmaker[Session], settings: Settings) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_session_factory] = lambda: sf
    application.dependency_overrides[get_app_settings] = lambda: settings
    return application


@pytest.fixture
def make_user(sf: sessionmaker[Session]) -> Callable[[str, str], int]:
    def _make(login: str, role: str) -> int:
        with sf() as s:
            u = models.User(login=login, password_hash=hash_password(PASSWORD), role=role)
            s.add(u)
            s.commit()
            return u.id

    return _make


@pytest.fixture
def anon(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def api_client(app: FastAPI, make_user: Callable[[str, str], int]) -> Iterator[ApiClientFactory]:
    clients: list[TestClient] = []

    def _client(role: str) -> TestClient:
        login = f"{role}-{len(clients)}"
        make_user(login, role)
        c = TestClient(app, raise_server_exceptions=False)
        clients.append(c)
        r = c.post("/api/auth/login", json={"login": login, "password": PASSWORD})
        assert r.status_code == 204, r.text
        return c

    yield _client
    for c in clients:
        c.close()
