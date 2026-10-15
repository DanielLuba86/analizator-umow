"""Sprzątanie po restarcie: analizy w tle nie przeżywają procesu (ADR 0007)."""

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.repo import analyses

INTERRUPTED_REASON = "przerwana_restartem"

log = structlog.get_logger(__name__)


def recover_interrupted_analyses(session_factory: sessionmaker[Session]) -> int:
    """Oznacza jako failed analizy, które zostały queued/running po poprzednim procesie.

    Zakłada jeden proces backendu (ADR 0007) — przy wielu workerach przerwałby cudze analizy.
    """
    with session_factory() as s:
        ids = analyses.fail_interrupted(s, INTERRUPTED_REASON)
        s.commit()
    if ids:
        log.warning("interrupted_analyses_failed", count=len(ids), analysis_ids=ids)
    return len(ids)
