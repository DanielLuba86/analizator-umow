from collections.abc import Callable

import pytest
from api_helpers import PASSWORD, ApiClientFactory, make_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_app_settings
from app.repo import models


def _audit(sf: sessionmaker[Session]) -> list[tuple[int | None, str]]:
    with sf() as s:
        rows = s.scalars(select(models.AuditLog).order_by(models.AuditLog.id))
        return [(r.user_id, r.akcja) for r in rows]


def test_login_sets_httponly_strict_cookie(
    app: FastAPI, anon: TestClient, make_user: Callable[[str, str], int]
) -> None:
    app.dependency_overrides[get_app_settings] = lambda: make_settings(cookie_secure=True)
    make_user("ala", "asystent")
    r = anon.post("/api/auth/login", json={"login": "ala", "password": PASSWORD})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("sid=")
    attrs = {a.strip().split("=")[0].lower() for a in cookie.split(";")[1:]}
    assert {"httponly", "secure", "path", "max-age"} <= attrs
    assert "samesite=strict" in cookie.lower()
    assert "path=/api" in cookie.lower()


def test_login_me_logout_roundtrip(
    anon: TestClient, make_user: Callable[[str, str], int], sf: sessionmaker[Session]
) -> None:
    uid = make_user("ola", "prawnik")
    assert (
        anon.post("/api/auth/login", json={"login": "ola", "password": PASSWORD}).status_code == 204
    )
    me = anon.get("/api/auth/me")
    assert me.status_code == 200 and me.json() == {"id": uid, "login": "ola", "role": "prawnik"}
    assert anon.post("/api/auth/logout").status_code == 204
    assert anon.get("/api/auth/me").status_code == 401
    assert (uid, "login") in _audit(sf) and (uid, "logout") in _audit(sf)


def test_logout_invalidates_session_server_side(
    anon: TestClient, make_user: Callable[[str, str], int]
) -> None:
    make_user("ewa", "asystent")
    anon.post("/api/auth/login", json={"login": "ewa", "password": PASSWORD})
    sid = anon.cookies.get("sid")
    assert sid
    anon.post("/api/auth/logout")
    anon.cookies.set("sid", sid, path="/api")  # ponowne użycie starego tokenu
    assert anon.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_user_same_401(
    anon: TestClient, make_user: Callable[[str, str], int], sf: sessionmaker[Session]
) -> None:
    make_user("jan", "asystent")
    wrong = anon.post("/api/auth/login", json={"login": "jan", "password": "zle-haslo"})
    unknown = anon.post("/api/auth/login", json={"login": "nikt", "password": "zle-haslo"})
    assert wrong.status_code == unknown.status_code == 401
    w, u = wrong.json(), unknown.json()
    assert w.pop("request_id") != u.pop("request_id")
    assert w == u
    assert "set-cookie" not in wrong.headers
    assert [a for _, a in _audit(sf)] == ["login_failed", "login_failed"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/auth/me"),
        ("GET", "/api/contracts"),
        ("POST", "/api/contracts"),
        ("GET", "/api/contracts/1"),
        ("POST", "/api/contracts/1/versions"),
        ("GET", "/api/versions/1"),
    ],
)
def test_endpoints_require_login(anon: TestClient, method: str, path: str) -> None:
    r = anon.request(method, path, json={})
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")


def test_garbage_cookie_is_401(anon: TestClient) -> None:
    anon.cookies.set("sid", "nie-istnieje", path="/api")
    assert anon.get("/api/auth/me").status_code == 401


def test_api_client_fixture_logs_in(api_client: ApiClientFactory) -> None:
    c = api_client("prawnik")
    assert c.get("/api/auth/me").json()["role"] == "prawnik"
