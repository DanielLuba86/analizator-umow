# ruff: noqa: S105
import logging
from typing import Any

import pytest
from api_helpers import ApiClientFactory
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.repo import models

TEXT = (
    "UMOWA NAJMU\n\nStrony: Wynajmujący i Najemca.\n\n"
    "§ 1. Przedmiot\nWynajmujący oddaje Najemcy lokal do używania.\n\n"
    "§ 2. Kary\nNajemca zapłaci karę umowną w wysokości 600 zł za każdy dzień zwłoki.\n"
)
SECRET = "POUFNE-POSTANOWIENIE-XYZ"


def payload(**kw: Any) -> dict[str, Any]:
    return {"title": "Najem lokalu", "kind": "najem", "source": "kontrahent", "text": TEXT} | kw


@pytest.fixture
def client(api_client: ApiClientFactory) -> TestClient:
    return api_client("asystent")


def assert_problem(r: Any, status: int) -> dict[str, Any]:
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = r.json()
    assert body["status"] == status
    assert isinstance(body["type"], str) and isinstance(body["title"], str)
    assert body["request_id"] == r.headers["x-request-id"]
    assert "detail" not in body
    return body


def test_create_contract_returns_fragments(client: TestClient) -> None:
    r = client.post("/api/contracts", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "version_id"}
    v = client.get(f"/api/versions/{body['version_id']}")
    assert v.status_code == 200
    data = v.json()
    assert data["nr"] == 1 and data["text"] == TEXT and data["contract_id"] == body["id"]
    frags = data["fragments"]
    assert [f["label"] for f in frags] == ["Komparycja", "§ 1", "§ 2"]
    assert frags[0]["start"] == 0 and frags[-1]["end"] == len(TEXT)
    assert set(frags[0]) == {"id", "label", "start", "end"}


def test_list_and_get_contract_with_versions(client: TestClient) -> None:
    cid = client.post("/api/contracts", json=payload(title="Umowa A")).json()["id"]
    r = client.post(f"/api/contracts/{cid}/versions", json={"text": TEXT + "\nAneks.\n"})
    assert r.status_code == 201 and r.json()["nr"] == 2 and "version_id" in r.json()
    listing = client.get("/api/contracts").json()
    (row,) = [c for c in listing if c["id"] == cid]
    assert row["title"] == "Umowa A" and row["versions"] == 2
    assert row["kind"] == "najem" and row["source"] == "kontrahent"
    detail = client.get(f"/api/contracts/{cid}").json()
    assert [v["nr"] for v in detail["versions"]] == [1, 2]
    assert "text" not in detail and all("text" not in v for v in detail["versions"])


def test_create_contract_writes_audit(client: TestClient, sf: sessionmaker[Session]) -> None:
    cid = client.post("/api/contracts", json=payload()).json()["id"]
    client.post(f"/api/contracts/{cid}/versions", json={"text": TEXT})
    with sf() as s:
        akcje = list(s.scalars(select(models.AuditLog.akcja).order_by(models.AuditLog.id)))
    assert akcje[-2:] == ["contract_create", "version_add"]


@pytest.mark.parametrize("text", ["", "   \n\t  "])
def test_empty_text_422(client: TestClient, text: str) -> None:
    assert_problem(client.post("/api/contracts", json=payload(text=text)), 422)
    cid = client.post("/api/contracts", json=payload()).json()["id"]
    assert_problem(client.post(f"/api/contracts/{cid}/versions", json={"text": text}), 422)


def test_too_long_text_413(client: TestClient, sf: sessionmaker[Session]) -> None:
    too_long = "a" * 2001  # max_contract_chars=2000 w ustawieniach testów
    with sf() as s:
        before = len(list(s.scalars(select(models.Contract.id))))
    assert_problem(client.post("/api/contracts", json=payload(text=too_long)), 413)
    with sf() as s:
        assert len(list(s.scalars(select(models.Contract.id)))) == before
    cid = client.post("/api/contracts", json=payload()).json()["id"]
    assert_problem(client.post(f"/api/contracts/{cid}/versions", json={"text": too_long}), 413)
    ok = client.post("/api/contracts", json=payload(text="a" * 2000))
    assert ok.status_code == 201


@pytest.mark.parametrize(
    "bad",
    [{"kind": "sprzedaż"}, {"source": "nieznane"}, {"title": ""}, {"title": "x" * 301}],
)
def test_invalid_fields_422(client: TestClient, bad: dict[str, Any]) -> None:
    assert_problem(client.post("/api/contracts", json=payload(**bad)), 422)


def test_unknown_ids_404(client: TestClient) -> None:
    assert_problem(client.get("/api/contracts/999999"), 404)
    assert_problem(client.get("/api/versions/999999"), 404)
    assert_problem(client.post("/api/contracts/999999/versions", json={"text": TEXT}), 404)


def test_error_body_is_problem_json_with_request_id_and_no_text(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    # 422 z treścią umowy w złym polu: odpowiedź nie może jej powtórzyć
    r = client.post("/api/contracts", json=payload(kind=SECRET, text=f"Umowa {SECRET}"))
    body = assert_problem(r, 422)
    assert SECRET not in r.text
    assert set(body) <= {"type", "title", "status", "request_id", "errors"}
    for e in body.get("errors", []):
        assert set(e) <= {"loc", "type"}
    # 413 też bez treści
    r = client.post("/api/contracts", json=payload(text=SECRET + "a" * 3000))
    assert_problem(r, 413)
    assert SECRET not in r.text
    assert SECRET not in caplog.text


def test_request_id_is_echoed_when_valid_and_generated_otherwise(client: TestClient) -> None:
    r = client.get("/api/contracts/999999", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123" and r.json()["request_id"] == "abc-123"
    r = client.get("/api/contracts/999999", headers={"X-Request-ID": "zly id <script>"})
    assert r.headers["x-request-id"] != "zly id <script>"
    assert len(r.headers["x-request-id"]) >= 16
    ok = client.get("/api/contracts")
    assert ok.headers["x-request-id"]


def test_malformed_json_is_problem_422(client: TestClient) -> None:
    r = client.post(
        "/api/contracts",
        content=b'{"title": "x", "text": "' + SECRET.encode(),
        headers={"content-type": "application/json"},
    )
    assert_problem(r, 422)
    assert SECRET not in r.text


def test_unhandled_error_is_problem_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import contracts as contracts_api

    def boom(*a: Any, **kw: Any) -> Any:
        raise RuntimeError(f"wyciek {SECRET}")

    monkeypatch.setattr(contracts_api.contracts_repo, "list_contracts", boom)
    r = client.get("/api/contracts")
    assert_problem(r, 500)
    assert SECRET not in r.text
