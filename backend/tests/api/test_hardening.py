"""Ochrony na poziomie HTTP: rozmiar ciała, nagłówek Origin, błędy bez współdzielonego stanu."""

import importlib
import pkgutil
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api
from app.api import deps
from app.api.errors import ApiError

LOGIN = {"login": "nikt", "password": "zle-haslo"}


def test_body_over_limit_413_before_parsing(anon: TestClient) -> None:
    r = anon.post(
        "/api/contracts",
        content=b"x" * (1_048_576 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["request_id"]


def test_post_with_foreign_origin_403(anon: TestClient) -> None:
    r = anon.post("/api/auth/login", json=LOGIN, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert r.json()["type"] == "/problems/obce_zrodlo"


def test_post_with_null_origin_403(anon: TestClient) -> None:
    r = anon.post("/api/auth/login", json=LOGIN, headers={"Origin": "null"})
    assert r.status_code == 403


def test_post_with_matching_origin_ok(anon: TestClient) -> None:
    r = anon.post(
        "/api/auth/login",
        json=LOGIN,
        headers={"Origin": "http://localhost:8080", "Host": "localhost:8080"},
    )
    assert r.status_code == 401  # doszło do logowania (złe hasło), nie zatrzymane na Origin


def test_post_without_origin_ok(anon: TestClient) -> None:
    assert anon.post("/api/auth/login", json=LOGIN).status_code == 401


def test_get_with_foreign_origin_ok(anon: TestClient) -> None:
    r = anon.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200


def test_no_module_level_api_error_instances() -> None:
    """Wyjątek współdzielony między żądaniami trzyma __traceback__ ostatniego żądania."""
    shared = []
    for info in pkgutil.iter_modules(app.api.__path__):
        module = importlib.import_module(f"app.api.{info.name}")
        shared += [f"{info.name}.{n}" for n, v in vars(module).items() if isinstance(v, ApiError)]
    assert shared == []


def test_session_factory_created_once_under_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[int] = []

    def slow_engine(url: str) -> Any:
        time.sleep(0.05)
        created.append(1)
        return object()

    monkeypatch.setattr(deps, "make_engine", slow_engine)
    monkeypatch.setattr(deps, "session_factory", lambda engine: object())
    request: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    settings: Any = SimpleNamespace(database_url="x")
    results: list[object] = []
    threads = [
        threading.Thread(target=lambda: results.append(deps.get_session_factory(request, settings)))
        for _ in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(created) == 1
    assert len({id(r) for r in results}) == 1
