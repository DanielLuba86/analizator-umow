import re

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.model import (
    ACTION_STATUSES,
    ACTION_TYPES,
    ANALYSIS_STATUSES,
    FINDING_TYPES,
    RISK_LEVELS,
)
from app.repo.models import (
    CONTRACT_KINDS,
    CONTRACT_SOURCES,
    REJECT_REASONS,
    ROLES,
    Analysis,
    Base,
    Contract,
    ContractVersion,
    Finding,
    Fragment,
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
        diffs = compare_metadata(
            MigrationContext.configure(conn, opts={"compare_server_default": True}),
            Base.metadata,
        )
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


def _finding(analysis_id: int, **kw: object) -> Finding:
    base: dict[str, object] = {
        "analysis_id": analysis_id, "typ": "kara", "teza": "t", "cytat": "c" * 12,
        "fragment_id": "f001", "start": 0, "end": 3, "uzasadnienie": "u",
    }  # fmt: skip
    return Finding(**{**base, **kw})


def test_check_constraints_match_domain_values(db_engine: Engine) -> None:
    expected: dict[str, tuple[str, ...]] = {
        "ck_users_role": ROLES,
        "ck_contracts_kind": CONTRACT_KINDS,
        "ck_contracts_source": CONTRACT_SOURCES,
        "ck_templates_kind": CONTRACT_KINDS,
        "ck_analyses_status": ANALYSIS_STATUSES,
        "ck_findings_typ": FINDING_TYPES,
        "ck_findings_poziom_ryzyka": RISK_LEVELS,
        "ck_rejected_claims_typ": FINDING_TYPES,
        "ck_rejected_claims_poziom_ryzyka": RISK_LEVELS,
        "ck_rejected_claims_powod": REJECT_REASONS,
        "ck_pending_actions_typ": ACTION_TYPES,
        "ck_pending_actions_status": ACTION_STATUSES,
    }
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='c' AND conrelid <> 0"  # noqa: E501
            )
        ).all()
    actual = {name: set(re.findall(r"'([^']*)'", definition)) for name, definition in rows}
    assert set(actual) == set(expected)
    for name, values in expected.items():
        assert actual[name] == set(values), name


def test_polish_diacritics_and_nullable_risk(db_session: Session) -> None:
    a = _analysis(db_session)
    v = db_session.get(ContractVersion, a.version_id)
    assert v is not None
    c = db_session.get(Contract, v.contract_id)
    assert c is not None
    c.source = "wewnętrzna"
    db_session.add(_finding(a.id, poziom_ryzyka="średnie"))
    db_session.add(_finding(a.id, poziom_ryzyka=None))
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(_finding(a.id, poziom_ryzyka="zbyt wysokie"))


def test_deleting_contract_cascades(db_session: Session) -> None:
    a = _analysis(db_session)
    v = db_session.get(ContractVersion, a.version_id)
    assert v is not None
    db_session.add(Fragment(version_id=v.id, frag_id="f001", label="§ 1", start=0, end=3))
    db_session.add(_finding(a.id))
    db_session.flush()
    db_session.execute(delete(Contract).where(Contract.id == v.contract_id))
    for model in (ContractVersion, Fragment, Analysis, Finding):
        assert db_session.scalars(select(model)).first() is None, model.__name__
