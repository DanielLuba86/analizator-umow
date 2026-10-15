from typing import Any

import pytest
from db_env import Env
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.repo import models
from app.services.recovery import recover_interrupted_analyses


def _set_status(env: Env, analysis_id: int, status: str) -> None:
    with env.sf() as s:
        s.get_one(models.Analysis, analysis_id).status = status
        s.commit()


def _status(env: Env, analysis_id: int) -> tuple[str, str | None, bool]:
    with env.sf() as s:
        a = s.get_one(models.Analysis, analysis_id)
        return a.status, a.reason, a.finished_at is not None


def test_interrupted_analyses_are_failed_and_finished_ones_untouched(env: Env) -> None:
    queued = env.tools().ctx.analysis_id
    running = env.tools().ctx.analysis_id
    done = env.tools().ctx.analysis_id
    _set_status(env, running, "running")
    _set_status(env, done, "done")
    assert recover_interrupted_analyses(env.sf) == 2
    assert _status(env, queued) == ("failed", "przerwana_restartem", True)
    assert _status(env, running) == ("failed", "przerwana_restartem", True)
    assert _status(env, done)[0] == "done"


def test_app_startup_runs_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def fake(sf: sessionmaker[Session]) -> int:
        calls.append(sf)
        return 0

    monkeypatch.setattr(main, "recover_interrupted_analyses", fake)
    with TestClient(main.create_app()):
        pass
    assert len(calls) == 1
    with TestClient(main.create_app(recover_interrupted=False)):
        pass
    assert len(calls) == 1
