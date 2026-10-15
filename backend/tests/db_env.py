"""Wspólne fixture'y testów z bazą: transakcja wycofywana po teście, fabryka sesji, Env."""

# ruff: noqa: S106
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.context import AnalysisContext
from app.agent.tools import AgentTools
from app.repo import models
from app.repo.analyses import create_analysis
from app.repo.contracts import add_contract, add_version

TEXT = (
    "UMOWA NAJMU\n\nStrony: Wynajmujący i Najemca.\n\n"
    "§ 1. Przedmiot\nWynajmujący oddaje Najemcy lokal do używania.\n\n"
    "§ 2. Kary\nNajemca zapłaci karę umowną w wysokości 600 zł za każdy dzień zwłoki.\n"
)
QUOTE = "zapłaci karę umowną w wysokości 600 zł"


@pytest.fixture
def conn(db_engine: Engine) -> Iterator[Connection]:
    c = db_engine.connect()
    outer = c.begin()
    try:
        yield c
    finally:
        outer.rollback()
        c.close()


@pytest.fixture
def sf(conn: Connection) -> sessionmaker[Session]:
    """Fabryka sesji: commit narzędzi zostaje w zewnętrznej, wycofywanej transakcji."""
    return sessionmaker(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)


class Env:
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self.sf = sf
        with sf() as s:
            u = models.User(login="agent-test", password_hash="x", role="prawnik")
            s.add(u)
            s.flush()
            self.user_id = u.id
            s.commit()

    def version(self, text: str = TEXT) -> int:
        with self.sf() as s:
            cid = add_contract(
                s, title="T", kind="najem", source="kontrahent", created_by=self.user_id
            )
            vid = add_version(s, cid, text)
            s.commit()
            return vid

    def tools(self, text: str = TEXT, max_findings: int = 60) -> AgentTools:
        vid = self.version(text)
        with self.sf() as s:
            aid = create_analysis(s, vid, self.user_id, "fake")
            s.commit()
        ctx = AnalysisContext(
            analysis_id=aid, version_id=vid, kind="najem", max_findings=max_findings
        )
        return AgentTools(ctx, self.sf)

    def count(self, model: Any, analysis_id: int) -> int:
        with self.sf() as s:
            return (
                s.scalar(
                    select(func.count()).select_from(model).where(model.analysis_id == analysis_id)
                )
                or 0
            )

    def count_rejected(self, analysis_id: int) -> int:
        return self.count(models.RejectedClaim, analysis_id)

    def count_findings(self, analysis_id: int) -> int:
        return self.count(models.Finding, analysis_id)

    def rejected_reasons(self, analysis_id: int) -> list[str]:
        with self.sf() as s:
            return list(
                s.scalars(
                    select(models.RejectedClaim.powod)
                    .where(models.RejectedClaim.analysis_id == analysis_id)
                    .order_by(models.RejectedClaim.id)
                )
            )

    def pending_types(self, analysis_id: int) -> list[str]:
        with self.sf() as s:
            return list(
                s.scalars(
                    select(models.PendingAction.typ)
                    .where(models.PendingAction.analysis_id == analysis_id)
                    .order_by(models.PendingAction.id)
                )
            )

    def templates_snapshot(self) -> list[tuple[int, str, str, str, int]]:
        with self.sf() as s:
            rows = s.scalars(select(models.Template).order_by(models.Template.id))
            return [(t.id, t.kind, t.nazwa_klauzuli, t.tresc, t.wersja) for t in rows]


@pytest.fixture
def env(sf: sessionmaker[Session]) -> Env:
    return Env(sf)
