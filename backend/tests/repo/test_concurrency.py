"""Wyścigi z Review Focus 4–5 na dwóch prawdziwych połączeniach (dwuklik, dwóch prawników).

Dane są zatwierdzane (inne połączenie musi je widzieć) i usuwane po teście.
"""

# ruff: noqa: S106
import asyncio
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.context import AnalysisContext
from app.agent.tools import AgentTools
from app.config import Settings
from app.repo import actions, analyses, models
from app.repo.actions import ActionAlreadyDecided
from app.repo.analyses import AnalysisAlreadyActive
from app.repo.contracts import add_contract, add_version, list_fragments
from app.repo.templates import add_template_version
from app.services import actions as actions_service

SETTINGS = Settings(database_url="postgresql+psycopg://u:p@localhost/db")
TEXT = (
    "UMOWA\n\n§ 1. Przedmiot\nWynajmujący oddaje Najemcy lokal do używania na czas nieoznaczony.\n"
)
LOCK_WAIT_S = 0.5


@dataclass
class Data:
    user_id: int
    contract_id: int
    version_id: int
    analysis_id: int


@pytest.fixture
def data(db_engine: Engine) -> Iterator[Data]:
    with Session(db_engine) as s:
        u = models.User(login="wyscig-prawnik", password_hash="x", role="prawnik")
        s.add(u)
        s.flush()
        cid = add_contract(s, title="Wyścig", kind="najem", source="kontrahent", created_by=u.id)
        vid = add_version(s, cid, TEXT)
        aid = analyses.create_analysis(s, vid, u.id, "fake")
        analyses.set_status(s, aid, "running")
        analyses.set_status(s, aid, "done")
        s.commit()
        d = Data(u.id, cid, vid, aid)
    try:
        yield d
    finally:
        with Session(db_engine) as s:
            s.execute(delete(models.Contract).where(models.Contract.id == d.contract_id))
            s.execute(delete(models.AuditLog).where(models.AuditLog.user_id == d.user_id))
            s.execute(delete(models.User).where(models.User.id == d.user_id))
            s.commit()


def race(
    db_engine: Engine, first: Callable[[Session], Any], second: Callable[[Session], Any]
) -> Any:
    """`first` trzyma blokadę w otwartej transakcji; `second` musi czekać, potem wynik/wyjątek."""
    s1 = Session(db_engine)
    result: dict[str, Any] = {}

    def run_second() -> None:
        with Session(db_engine) as s2:
            try:
                result["value"] = second(s2)
                s2.commit()
            except Exception as e:  # noqa: BLE001 - wynik testu
                s2.rollback()
                result["error"] = e

    try:
        first(s1)
        t = threading.Thread(target=run_second)
        t.start()
        t.join(LOCK_WAIT_S)
        assert t.is_alive(), "drugie żądanie powinno czekać na blokadę pierwszego"
        s1.commit()
        t.join(10)
        assert not t.is_alive()
    finally:
        s1.close()
    return result


def test_double_start_same_version_second_gets_already_active(
    db_engine: Engine, data: Data
) -> None:
    with Session(db_engine) as s:  # poprzednia analiza zakończona, więc start jest dozwolony
        assert analyses.active_analysis(s, data.version_id) is None

    def start(s: Session) -> int:
        return analyses.create_analysis(s, data.version_id, data.user_id, "fake")

    result = race(db_engine, start, start)
    assert isinstance(result.get("error"), AnalysisAlreadyActive)
    with Session(db_engine) as s:
        n = s.scalar(
            select(func.count())
            .select_from(models.Analysis)
            .where(
                models.Analysis.version_id == data.version_id, models.Analysis.status == "queued"
            )
        )
    assert n == 1


def test_two_lawyers_approve_export_once(db_engine: Engine, data: Data) -> None:
    with Session(db_engine) as s:
        action_id = actions.request_action(s, data.analysis_id, "eksport", {"zrodlo": "test"})
        s.commit()

    def approve(s: Session) -> Any:
        action = actions.get_action(s, action_id)
        assert action is not None
        return actions_service.decide(
            s, action, decided_by=data.user_id, approve=True, settings=SETTINGS
        )

    result = race(db_engine, approve, approve)
    assert isinstance(result.get("error"), ActionAlreadyDecided)
    with Session(db_engine) as s:
        exports = s.scalar(
            select(func.count())
            .select_from(models.Export)
            .where(models.Export.action_id == action_id)
        )
        audits = s.scalar(
            select(func.count())
            .select_from(models.AuditLog)
            .where(
                models.AuditLog.akcja == "decyzja:eksport:true",
                models.AuditLog.obiekt == f"action:{action_id}",
            )
        )
    assert (exports, audits) == (1, 1)


def test_concurrent_identical_requests_return_one_pending_action(
    db_engine: Engine, data: Data
) -> None:
    def request(s: Session) -> int:
        analysis = analyses.get_analysis(s, data.analysis_id)
        assert analysis is not None
        return actions_service.request_user_action(s, analysis, "eksport", data.user_id)

    with Session(db_engine) as s1:
        first_id = request(s1)  # wiersz wstawiony, transakcja otwarta (unikat częściowy zajęty)
        result: dict[str, Any] = {}

        def second() -> None:
            with Session(db_engine) as s2:
                result["id"] = request(s2)
                s2.commit()

        t = threading.Thread(target=second)
        t.start()
        t.join(LOCK_WAIT_S)
        assert t.is_alive(), "drugi INSERT powinien czekać na unikat z pierwszej transakcji"
        s1.commit()
        t.join(10)
    assert result["id"] == first_id
    with Session(db_engine) as s:
        n = s.scalar(
            select(func.count())
            .select_from(models.PendingAction)
            .where(models.PendingAction.analysis_id == data.analysis_id)
        )
    assert n == 1


def test_add_template_version_concurrent(db_engine: Engine) -> None:
    name = "Wyścig wersji wzorca"
    try:
        result = race(
            db_engine,
            lambda s: add_template_version(s, "najem", name, "pierwsza"),
            lambda s: add_template_version(s, "najem", name, "druga"),
        )
        assert "error" not in result, result.get("error")
        assert result["value"] == 2
        with Session(db_engine) as s:
            versions = sorted(
                s.scalars(
                    select(models.Template.wersja).where(models.Template.nazwa_klauzuli == name)
                )
            )
        assert versions == [1, 2]
    finally:
        with Session(db_engine) as s:
            s.execute(delete(models.Template).where(models.Template.nazwa_klauzuli == name))
            s.commit()


def test_submit_finding_waits_for_analysis_row_lock(db_engine: Engine, data: Data) -> None:
    """Liczenie tez i zapis są pod blokadą wiersza analizy (limit nie do obejścia wyścigiem)."""
    with Session(db_engine) as s:
        frag = list_fragments(s, data.version_id)[-1]  # § 1 z cytowanym zdaniem
    ctx = AnalysisContext(data.analysis_id, data.version_id, "najem", max_findings=60)
    tools = AgentTools(ctx, sessionmaker(db_engine))

    def lock(s: Session) -> None:
        s.execute(
            select(models.Analysis.id)
            .where(models.Analysis.id == data.analysis_id)
            .with_for_update(key_share=True)  # FOR NO KEY UPDATE: nie koliduje z KEY SHARE z FK
        ).one()

    def submit(_: Session) -> Any:
        return asyncio.run(
            tools.submit_finding(
                "termin",
                "Czas nieoznaczony",
                "lokal do używania na czas nieoznaczony",
                frag.id,
                "Uzasadnienie.",
            )
        )

    result = race(db_engine, lock, submit)
    assert result["value"]["is_error"] is False
