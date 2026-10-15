# ruff: noqa: S106
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from api_helpers import ApiClientFactory, make_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.classifier import ClassifierHit, FakeClassifier
from app.agent.fake_runner import FakeAgentRunner, ToolCall
from app.api.analyses import get_classifier, get_runner
from app.config import Settings
from app.repo import models
from app.repo.actions import decide_action
from app.repo.analyses import create_analysis

DATA = Path(__file__).resolve().parents[3] / "data"
INJECTED = (DATA / "umowy_z_wstrzyknieciem" / "jawne_polecenie.md").read_text(encoding="utf-8")
TEXT = (
    "UMOWA NAJMU\n\nStrony: Wynajmujący i Najemca.\n\n"
    "§ 1. Przedmiot\nWynajmujący oddaje Najemcy lokal do używania.\n\n"
    "§ 2. Kary\nNajemca zapłaci karę umowną w wysokości 600 zł za każdy dzień zwłoki.\n"
)
TEXT_V2 = TEXT.replace("600 zł", "900 zł")
QUOTE = "zapłaci karę umowną w wysokości 600 zł"
QUOTE_V2 = "zapłaci karę umowną w wysokości 900 zł"
FABRICATED = "Najemca może wypowiedzieć umowę bez kary w każdym czasie"


def finding(cytat: str, fragment_id: str = "f003") -> ToolCall:
    return ToolCall(
        "submit_finding",
        {
            "typ": "kara",
            "teza": "Kara umowna za zwłokę",
            "cytat": cytat,
            "fragment_id": fragment_id,
            "uzasadnienie": "Wysoka kara dzienna.",
            "poziom_ryzyka": "wysokie",
        },
    )


class Agent:
    """Ustawia skrypt fałszywego agenta i klasyfikatora dla kolejnych analiz."""

    def __init__(self, app: FastAPI) -> None:
        self.script: Sequence[ToolCall] = []
        self.hits: list[ClassifierHit] | Exception = []
        app.dependency_overrides[get_runner] = lambda: FakeAgentRunner(
            self.script, max_turns=30, max_budget_usd=0.5, timeout_s=5.0
        )
        app.dependency_overrides[get_classifier] = lambda: FakeClassifier(self.hits)


@pytest.fixture
def settings() -> Settings:
    return make_settings(max_contract_chars=200_000)  # umowy z korpusu są dłuższe niż 2000


@pytest.fixture
def agent(app: FastAPI) -> Agent:
    return Agent(app)


@pytest.fixture
def client(api_client: ApiClientFactory) -> TestClient:
    return api_client("asystent")


def new_version(client: TestClient, text: str = TEXT) -> int:
    r = client.post(
        "/api/contracts",
        json={"title": "Najem", "kind": "najem", "source": "kontrahent", "text": text},
    )
    assert r.status_code == 201
    vid: int = r.json()["version_id"]
    return vid


def start(client: TestClient, version_id: int) -> int:
    r = client.post(f"/api/versions/{version_id}/analyses")
    assert r.status_code == 202, r.text
    aid: int = r.json()["analysis_id"]
    return aid


def test_start_analysis_runs_and_reports_done(client: TestClient, agent: Agent) -> None:
    agent.script = [ToolCall("list_fragments"), finding(QUOTE)]
    aid = start(client, new_version(client))
    r = client.get(f"/api/analyses/{aid}")
    assert r.status_code == 200
    rep = r.json()
    assert rep["status"] == "done" and rep["turns"] == 2
    assert rep["cost_usd"] == pytest.approx(0.02)
    assert rep["quarantine"] is None and rep["incomplete"] is False
    (f,) = rep["findings"]
    assert f["cytat"] == QUOTE and f["typ"] == "kara" and f["fragment_id"] == "f003"
    assert TEXT[f["start"] : f["end"]] == QUOTE


def test_second_start_while_running_409(
    client: TestClient, agent: Agent, sf: sessionmaker[Session]
) -> None:
    vid = new_version(client)
    with sf() as s:
        uid = s.scalar(select(models.User.id).where(models.User.login.like("asystent-%")))
        assert uid is not None
        create_analysis(s, vid, uid, "fake")  # status queued
        s.commit()
    r = client.post(f"/api/versions/{vid}/analyses")
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_new_analysis_allowed_after_previous_finished(client: TestClient, agent: Agent) -> None:
    vid = new_version(client)
    first = start(client, vid)
    second = start(client, vid)
    assert second != first


def test_version_lists_its_analyses_newest_first(client: TestClient, agent: Agent) -> None:
    vid = new_version(client)
    assert client.get(f"/api/versions/{vid}").json()["analyses"] == []
    first = start(client, vid)
    second = start(client, vid)
    analyses = client.get(f"/api/versions/{vid}").json()["analyses"]
    assert [a["id"] for a in analyses] == [second, first]
    assert all(a["status"] == "done" for a in analyses)
    assert set(analyses[0]) == {"id", "status", "started_at"}


def test_start_unknown_version_404(client: TestClient, agent: Agent) -> None:
    assert client.post("/api/versions/999999/analyses").status_code == 404
    assert client.get("/api/analyses/999999").status_code == 404


def test_quarantined_report_hidden(
    client: TestClient, agent: Agent, sf: sessionmaker[Session]
) -> None:
    agent.script = [finding(QUOTE)]
    aid = start(client, new_version(client, INJECTED))
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "quarantined"
    assert rep["findings"] == []
    action_id = rep["quarantine"]["action_id"]
    assert rep["quarantine"]["status"] == "oczekuje"
    # po zatwierdzeniu wniosku przez prawnika raport jest widoczny
    with sf() as s:
        lawyer = models.User(login="prawnik-x", password_hash="x", role="prawnik")
        s.add(lawyer)
        s.flush()
        decide_action(s, action_id, lawyer.id, approve=True)
        s.commit()
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "quarantined"
    assert rep["quarantine"] == {"action_id": action_id, "status": "zatwierdzona"}
    assert any(f["typ"] == "wstrzyknięcie" for f in rep["findings"])


def test_quarantine_rejected_keeps_report_hidden(
    client: TestClient, agent: Agent, sf: sessionmaker[Session]
) -> None:
    aid = start(client, new_version(client, INJECTED))
    action_id = client.get(f"/api/analyses/{aid}").json()["quarantine"]["action_id"]
    with sf() as s:
        lawyer = models.User(login="prawnik-y", password_hash="x", role="prawnik")
        s.add(lawyer)
        s.flush()
        decide_action(s, action_id, lawyer.id, approve=False)
        s.commit()
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["findings"] == [] and rep["quarantine"]["status"] == "odrzucona"


def test_classifier_failure_quarantines_via_api(client: TestClient, agent: Agent) -> None:
    from app.agent.classifier import ClassifierUnavailable

    agent.hits = ClassifierUnavailable()
    agent.script = [finding(QUOTE)]
    aid = start(client, new_version(client))
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "quarantined" and rep["findings"] == []


def test_running_analysis_shows_no_findings(
    client: TestClient, agent: Agent, sf: sessionmaker[Session]
) -> None:
    agent.script = [finding(QUOTE)]
    aid = start(client, new_version(client))
    with sf() as s:
        s.get_one(models.Analysis, aid).status = "running"
        s.commit()
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "running" and rep["findings"] == []


def test_budget_exceeded_marks_report_incomplete(client: TestClient, app: FastAPI) -> None:
    app.dependency_overrides[get_runner] = lambda: FakeAgentRunner(
        [finding(QUOTE), ToolCall("list_fragments")], max_turns=1, max_budget_usd=0.5, timeout_s=5
    )
    app.dependency_overrides[get_classifier] = lambda: FakeClassifier([])
    aid = start(client, new_version(client))
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "budget_exceeded" and rep["incomplete"] is True
    assert len(rep["findings"]) == 1


def test_rejected_claims_never_in_response(client: TestClient, agent: Agent) -> None:
    agent.script = [finding(QUOTE), finding(FABRICATED), finding(QUOTE, fragment_id="f999")]
    aid = start(client, new_version(client))
    r = client.get(f"/api/analyses/{aid}")
    assert FABRICATED not in r.text
    rep = r.json()
    assert "rejected_claims" not in rep and "rejected" not in rep
    assert [f["cytat"] for f in rep["findings"]] == [QUOTE]


def test_comparison_lists_changed_fragment(client: TestClient, agent: Agent) -> None:
    v1 = new_version(client)
    cid = client.get(f"/api/versions/{v1}").json()["contract_id"]
    v2 = client.post(f"/api/contracts/{cid}/versions", json={"text": TEXT_V2}).json()["version_id"]
    # bez analiz: finding_changes = null
    r = client.post("/api/comparisons", json={"version_a": v1, "version_b": v2})
    assert r.status_code == 201
    body = r.json()
    assert body["finding_changes"] is None
    assert body["fragment_changes"] == [
        {
            "label": "§ 2",
            "kind": "zmieniony",
            "old_text": next(f for f in _frags(client, v1) if f[0] == "§ 2")[1],
            "new_text": next(f for f in _frags(client, v2) if f[0] == "§ 2")[1],
        }
    ]
    # z analizami done obu wersji: zmiana tezy
    agent.script = [finding(QUOTE)]
    start(client, v1)
    agent.script = [finding(QUOTE_V2)]
    start(client, v2)
    body = client.post("/api/comparisons", json={"version_a": v1, "version_b": v2}).json()
    assert body["finding_changes"] == {
        "nowe": [{"typ": "kara", "label": "§ 2", "cytat": QUOTE_V2}],
        "ustąpiło": [{"typ": "kara", "label": "§ 2", "cytat": QUOTE}],
    }


def test_comparison_validation(client: TestClient, agent: Agent) -> None:
    v1 = new_version(client)
    other = new_version(client)
    r = client.post("/api/comparisons", json={"version_a": v1, "version_b": 999999})
    assert r.status_code == 404
    r = client.post("/api/comparisons", json={"version_a": v1, "version_b": other})
    assert r.status_code == 422


def test_analysis_endpoints_require_login(anon: TestClient) -> None:
    assert anon.post("/api/versions/1/analyses").status_code == 401
    assert anon.get("/api/analyses/1").status_code == 401
    assert anon.post("/api/comparisons", json={"version_a": 1, "version_b": 2}).status_code == 401


def _frags(client: TestClient, vid: int) -> list[tuple[str, str]]:
    data: dict[str, Any] = client.get(f"/api/versions/{vid}").json()
    return [(f["label"], data["text"][f["start"] : f["end"]]) for f in data["fragments"]]


def test_failed_analysis_with_injection_finding_stays_hidden(
    client: TestClient, agent: Agent, sf: sessionmaker[Session]
) -> None:
    """Obrona w głąb: status failed nie może odsłonić tez analizy z wykrytym wstrzyknięciem."""
    agent.script = [finding(QUOTE)]
    aid = start(client, new_version(client, INJECTED))
    with sf() as s:
        a = s.get_one(models.Analysis, aid)
        a.status = "failed"
        for p in s.scalars(
            select(models.PendingAction).where(models.PendingAction.analysis_id == aid)
        ):
            s.delete(p)
        s.commit()
    rep = client.get(f"/api/analyses/{aid}").json()
    assert rep["status"] == "failed" and rep["findings"] == []
    assert client.post(f"/api/analyses/{aid}/actions", json={"typ": "eksport"}).status_code == 409
