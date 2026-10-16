# ruff: noqa: S106
from pathlib import Path
from typing import Any

import pytest
from api_helpers import ApiClientFactory, make_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.classifier import FakeClassifier
from app.agent.fake_runner import FakeAgentRunner, ToolCall
from app.api.analyses import get_classifier, get_runner
from app.config import Settings
from app.repo import models
from app.repo.actions import request_action

DATA = Path(__file__).resolve().parents[3] / "data"
INJECTED = (DATA / "umowy_z_wstrzyknieciem" / "jawne_polecenie.md").read_text(encoding="utf-8")
TEXT = (
    "UMOWA NAJMU\n\nStrony: Wynajmujący i Najemca.\n\n"
    "§ 1. Przedmiot\nWynajmujący oddaje Najemcy lokal do używania.\n\n"
    "§ 2. Kary\nNajemca zapłaci karę umowną w wysokości 600 zł za każdy dzień zwłoki.\n"
)
QUOTE = "zapłaci karę umowną w wysokości 600 zł"
FABRICATED = "Najemca może wypowiedzieć umowę bez kary w każdym czasie"
SCRIPT = [
    ToolCall(
        "submit_finding",
        {
            "typ": "kara",
            "teza": "Kara umowna za zwłokę",
            "cytat": cytat,
            "fragment_id": "f003",
            "uzasadnienie": "Wysoka kara dzienna.",
            "poziom_ryzyka": "wysokie",
        },
    )
    for cytat in (QUOTE, FABRICATED)
]


@pytest.fixture
def settings() -> Settings:
    return make_settings(max_contract_chars=200_000)


@pytest.fixture(autouse=True)
def fake_agent(app: FastAPI) -> None:
    app.dependency_overrides[get_runner] = lambda: FakeAgentRunner(
        SCRIPT, max_turns=30, max_budget_usd=0.5, timeout_s=5.0
    )
    app.dependency_overrides[get_classifier] = lambda: FakeClassifier([])


@pytest.fixture
def assistant(api_client: ApiClientFactory) -> TestClient:
    return api_client("asystent")


@pytest.fixture
def lawyer(api_client: ApiClientFactory) -> TestClient:
    return api_client("prawnik")


def analysis(client: TestClient, text: str = TEXT) -> int:
    r = client.post(
        "/api/contracts",
        json={"title": "Najem", "kind": "najem", "source": "kontrahent", "text": text},
    )
    vid = r.json()["version_id"]
    r = client.post(f"/api/versions/{vid}/analyses")
    assert r.status_code == 202, r.text
    aid: int = r.json()["analysis_id"]
    return aid


def request(client: TestClient, aid: int, typ: str) -> int:
    r = client.post(f"/api/analyses/{aid}/actions", json={"typ": typ})
    assert r.status_code in (200, 201), r.text
    action_id: int = r.json()["action_id"]
    return action_id


def decide(client: TestClient, action_id: int, approve: bool, **extra: Any) -> Any:
    return client.post(f"/api/actions/{action_id}/decision", json={"approve": approve, **extra})


def audit_actions(sf: sessionmaker[Session]) -> list[str]:
    with sf() as s:
        return list(s.scalars(select(models.AuditLog.akcja).order_by(models.AuditLog.id)))


def test_assistant_cannot_decide_403(assistant: TestClient, sf: sessionmaker[Session]) -> None:
    aid = analysis(assistant)
    action_id = request(assistant, aid, "opinia")
    r = decide(assistant, action_id, True)
    assert r.status_code == 403
    assert r.headers["content-type"].startswith("application/problem+json")
    report = assistant.get(f"/api/analyses/{aid}").json()
    assert report["official"] is False
    assert not any(a.startswith("decyzja:") for a in audit_actions(sf))


def test_lawyer_approves_opinion_marks_official(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant)
    action_id = request(assistant, aid, "opinia")
    pending = lawyer.get("/api/actions", params={"status": "oczekuje"}).json()
    assert [(a["id"], a["typ"], a["analysis_id"]) for a in pending] == [(action_id, "opinia", aid)]
    r = decide(lawyer, action_id, True)
    assert r.status_code == 200 and r.json()["status"] == "zatwierdzona"
    assert assistant.get(f"/api/analyses/{aid}").json()["official"] is True
    assert lawyer.get("/api/actions", params={"status": "oczekuje"}).json() == []
    assert "decyzja:opinia:true" in audit_actions(sf)


def test_lawyer_approves_quarantine_unlocks_report(
    assistant: TestClient, lawyer: TestClient
) -> None:
    aid = analysis(assistant, INJECTED)
    rep = assistant.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "quarantined" and rep["findings"] == []
    action_id = rep["quarantine"]["action_id"]
    r = decide(lawyer, action_id, True)
    assert r.status_code == 200
    rep = assistant.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "done"
    assert rep["quarantine"] == {"action_id": action_id, "status": "zatwierdzona"}
    assert rep["findings"]


def test_rejected_quarantine_keeps_report_hidden(assistant: TestClient, lawyer: TestClient) -> None:
    aid = analysis(assistant, INJECTED)
    action_id = assistant.get(f"/api/analyses/{aid}").json()["quarantine"]["action_id"]
    assert decide(lawyer, action_id, False).status_code == 200
    rep = assistant.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "quarantined" and rep["findings"] == []


def test_second_decision_409_and_single_audit_entry(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant)
    action_id = request(assistant, aid, "eksport")
    assert decide(lawyer, action_id, True).status_code == 200
    second = decide(lawyer, action_id, True)
    assert second.status_code == 409
    assert decide(lawyer, action_id, False).status_code == 409
    assert audit_actions(sf).count("decyzja:eksport:true") == 1
    assert not any(a.startswith("decyzja:eksport:false") for a in audit_actions(sf))
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(models.Export)) == 1


def test_template_change_applied_only_after_approval(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant)
    with sf() as s:  # wniosek agenta (request_action z narzędzia)
        action_id = request_action(
            s, aid, "wzorzec", {"uzasadnienie": "Brak wzorca kary", "zrodlo": "agent"}
        )
        s.commit()

    def versions() -> list[tuple[str, int, str]]:
        with sf() as s:
            rows = s.scalars(
                select(models.Template).where(models.Template.nazwa_klauzuli == "Kara za zwłokę")
            )
            return [(t.kind, t.wersja, t.tresc) for t in rows]

    assert versions() == []
    # zatwierdzenie wzorca wymaga treści klauzuli od prawnika
    assert decide(lawyer, action_id, True).status_code == 422
    assert versions() == []
    template = {"nazwa_klauzuli": "Kara za zwłokę", "tresc": "Kara 100 zł za dzień zwłoki."}
    r = decide(lawyer, action_id, True, template=template)
    assert r.status_code == 200
    assert versions() == [("najem", 1, "Kara 100 zł za dzień zwłoki.")]


def test_rejected_template_change_not_applied(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant)
    with sf() as s:
        action_id = request_action(s, aid, "wzorzec", {"uzasadnienie": "x", "zrodlo": "agent"})
        s.commit()
        before = s.scalar(select(func.count()).select_from(models.Template))
    assert decide(lawyer, action_id, False).status_code == 200
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(models.Template)) == before


def test_export_only_after_approval(
    assistant: TestClient, lawyer: TestClient, anon: TestClient
) -> None:
    aid = analysis(assistant)
    action_id = request(assistant, aid, "eksport")
    listed = assistant.get("/api/actions").json()
    (item,) = [a for a in listed if a["id"] == action_id]
    assert item["export_id"] is None
    r = decide(lawyer, action_id, True)
    export_id = r.json()["export_id"]
    assert isinstance(export_id, int)
    assert anon.get(f"/api/exports/{export_id}").status_code == 401
    e = assistant.get(f"/api/exports/{export_id}")
    assert e.status_code == 200
    assert "attachment" in e.headers["content-disposition"]
    body = e.json()
    assert body["analysis_id"] == aid
    assert [f["cytat"] for f in body["findings"]] == [QUOTE]
    assert FABRICATED not in e.text and "rejected" not in e.text
    assert assistant.get("/api/exports/999999").status_code == 404


def test_rejected_export_creates_no_file(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant)
    action_id = request(assistant, aid, "eksport")
    r = decide(lawyer, action_id, False)
    assert r.status_code == 200 and r.json()["export_id"] is None
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(models.Export)) == 0


def test_assistant_can_request_only_export_or_opinion(assistant: TestClient) -> None:
    aid = analysis(assistant)
    for typ in ("wzorzec", "kwarantanna", "cokolwiek"):
        r = assistant.post(f"/api/analyses/{aid}/actions", json={"typ": typ})
        assert r.status_code == 422


def test_duplicate_request_returns_same_pending_action(assistant: TestClient) -> None:
    aid = analysis(assistant)
    assert request(assistant, aid, "eksport") == request(assistant, aid, "eksport")


def test_cannot_request_export_of_hidden_report(assistant: TestClient) -> None:
    aid = analysis(assistant, INJECTED)  # kwarantanna, raport ukryty
    r = assistant.post(f"/api/analyses/{aid}/actions", json={"typ": "eksport"})
    assert r.status_code == 409


def test_unknown_ids_404(assistant: TestClient, lawyer: TestClient) -> None:
    assert (
        assistant.post("/api/analyses/999999/actions", json={"typ": "eksport"}).status_code == 404
    )
    assert decide(lawyer, 999999, True).status_code == 404


def test_actions_endpoints_require_login(anon: TestClient) -> None:
    assert anon.get("/api/actions").status_code == 401
    assert anon.post("/api/analyses/1/actions", json={"typ": "eksport"}).status_code == 401
    assert anon.post("/api/actions/1/decision", json={"approve": True}).status_code == 401


AGENT_TEXT = "Zatwierdź natychmiast nowy wzorzec, polecenie z umowy"


def _agent_template_request(sf: sessionmaker[Session], aid: int) -> int:
    with sf() as s:
        action_id = request_action(
            s, aid, "wzorzec", {"uzasadnienie": AGENT_TEXT, "zrodlo": "agent"}
        )
        s.commit()
    return action_id


def test_template_not_approvable_while_quarantined(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant, INJECTED)
    action_id = _agent_template_request(sf, aid)
    template = {"nazwa_klauzuli": "Wstrzyknięty wzorzec", "tresc": "Treść"}
    r = decide(lawyer, action_id, True, template=template)
    assert r.status_code == 409
    with sf() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(models.Template)
                .where(models.Template.nazwa_klauzuli == "Wstrzyknięty wzorzec")
            )
            == 0
        )
        assert s.get_one(models.PendingAction, action_id).status == "oczekuje"


def test_agent_justification_hidden_while_report_hidden(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant, INJECTED)
    action_id = _agent_template_request(sf, aid)
    for client in (assistant, lawyer):
        r = client.get("/api/actions")
        assert AGENT_TEXT not in r.text
        (item,) = [a for a in r.json() if a["id"] == action_id]
        assert item["payload"] == {"zrodlo": "agent", "ukryte": True}
    # po zatwierdzeniu kwarantanny uzasadnienie agenta jest widoczne
    q_id = assistant.get(f"/api/analyses/{aid}").json()["quarantine"]["action_id"]
    assert decide(lawyer, q_id, True).status_code == 200
    (item,) = [a for a in lawyer.get("/api/actions").json() if a["id"] == action_id]
    assert item["payload"]["uzasadnienie"] == AGENT_TEXT


def test_new_action_returns_201_existing_pending_returns_200(assistant: TestClient) -> None:
    aid = analysis(assistant)
    first = assistant.post(f"/api/analyses/{aid}/actions", json={"typ": "eksport"})
    second = assistant.post(f"/api/analyses/{aid}/actions", json={"typ": "eksport"})
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json()


def test_template_with_rejection_422(
    assistant: TestClient, lawyer: TestClient, sf: sessionmaker[Session]
) -> None:
    aid = analysis(assistant)
    action_id = _agent_template_request(sf, aid)
    template = {"nazwa_klauzuli": "Kara", "tresc": "Kara 100 zł."}
    r = decide(lawyer, action_id, False, template=template)
    assert r.status_code == 422
    assert r.json()["type"] == "/problems/wzorzec_niedozwolony"


def test_template_for_non_wzorzec_422(assistant: TestClient, lawyer: TestClient) -> None:
    aid = analysis(assistant)
    action_id = request(assistant, aid, "eksport")
    template = {"nazwa_klauzuli": "Kara", "tresc": "Kara 100 zł."}
    r = decide(lawyer, action_id, True, template=template)
    assert r.status_code == 422
    assert r.json()["type"] == "/problems/wzorzec_niedozwolony"


def test_export_headers(assistant: TestClient, lawyer: TestClient) -> None:
    aid = analysis(assistant)
    export_id = decide(lawyer, request(assistant, aid, "eksport"), True).json()["export_id"]
    e = assistant.get(f"/api/exports/{export_id}")
    assert e.headers["x-content-type-options"] == "nosniff"
    assert e.headers["cache-control"] == "no-store"


def test_list_actions_filter_by_analysis(assistant: TestClient) -> None:
    a1, a2 = analysis(assistant), analysis(assistant)
    id1, id2 = request(assistant, a1, "eksport"), request(assistant, a2, "eksport")
    listed = assistant.get(f"/api/actions?analysis_id={a1}").json()
    assert [a["id"] for a in listed] == [id1]
    both = assistant.get("/api/actions").json()
    assert {id1, id2} <= {a["id"] for a in both}
    assert assistant.get("/api/actions?analysis_id=abc").status_code == 422
