import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repo.models import (
    Analysis,
    Base,
    Contract,
    ContractVersion,
    PendingAction,
    User,
)

EXPECTED_TABLES = {
    "users", "contracts", "contract_versions", "fragments", "analyses", "findings",
    "rejected_claims", "templates", "comparisons", "pending_actions", "audit_log",
    "sessions", "exports",
}  # fmt: skip


def _analysis(s: Session) -> Analysis:
    user = User(login="u1", password_hash="x", role="prawnik")  # noqa: S106
    s.add(user)
    s.flush()
    contract = Contract(title="Umowa", kind="najem", source="wewnętrzna", created_by=user.id)
    s.add(contract)
    s.flush()
    version = ContractVersion(contract_id=contract.id, nr=1, text="abc", sha256="0" * 64)
    s.add(version)
    s.flush()
    analysis = Analysis(version_id=version.id, status="queued", model="m", started_by=user.id)
    s.add(analysis)
    s.flush()
    return analysis


def test_migration_creates_all_tables(db_engine: Engine) -> None:
    names = set(inspect(db_engine).get_table_names()) - {"alembic_version"}
    assert names == EXPECTED_TABLES


def test_models_match_migration(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diffs == []


def test_version_number_unique_per_contract(db_session: Session) -> None:
    a = _analysis(db_session)
    v = db_session.get(ContractVersion, a.version_id)
    assert v is not None
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(ContractVersion(contract_id=v.contract_id, nr=1, text="x", sha256="1" * 64))


def test_only_one_pending_action_per_type(db_session: Session) -> None:
    a = _analysis(db_session)
    db_session.add(PendingAction(typ="opinia", analysis_id=a.id))
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(PendingAction(typ="opinia", analysis_id=a.id))
    # inny typ albo rozstrzygnięty status nie koliduje
    db_session.add(PendingAction(typ="eksport", analysis_id=a.id))
    db_session.add(PendingAction(typ="opinia", analysis_id=a.id, status="odrzucona"))
    db_session.flush()


def test_enum_check_rejects_bad_status(db_session: Session) -> None:
    a = _analysis(db_session)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(PendingAction(typ="opinia", analysis_id=a.id, status="zły"))
        db_session.flush()
