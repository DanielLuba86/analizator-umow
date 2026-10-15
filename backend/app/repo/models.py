"""Modele ORM — schemat trwały aplikacji (spec § 3)."""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any, get_args

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.fragments import MAX_FRAGMENT_ID_LEN
from app.domain.model import (
    ACTION_STATUSES,
    ACTION_TYPES,
    ANALYSIS_STATUSES,
    CONTRACT_KINDS,
    CONTRACT_SOURCES,
    FINDING_TYPES,
    RISK_LEVELS,
    ROLES,
)
from app.domain.quotes import RejectReason

REJECT_REASONS: tuple[str, ...] = get_args(RejectReason)


def _in(column: str, values: Iterable[str], name: str, nullable: bool = False) -> CheckConstraint:
    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    cond = f"{column} IN ({quoted})"
    if nullable:
        cond = f"{column} IS NULL OR {cond}"
    return CheckConstraint(cond, name=name)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _fk(target: str, *, nullable: bool = False, cascade: bool = True) -> Mapped[Any]:
    return mapped_column(
        ForeignKey(target, ondelete="CASCADE" if cascade else None), nullable=nullable
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (_in("role", ROLES, "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        _in("kind", CONTRACT_KINDS, "kind"),
        _in("source", CONTRACT_SOURCES, "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[int] = _fk("users.id", cascade=False)


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint("contract_id", "nr", name="uq_contract_versions_contract_id_nr"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = _fk("contracts.id")
    nr: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


class Fragment(Base):
    __tablename__ = "fragments"
    __table_args__ = (
        UniqueConstraint("version_id", "frag_id", name="uq_fragments_version_id_frag_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = _fk("contract_versions.id")
    frag_id: Mapped[str] = mapped_column(String(MAX_FRAGMENT_ID_LEN))
    label: Mapped[str] = mapped_column(String(200))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (_in("status", ANALYSIS_STATUSES, "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = _fk("contract_versions.id")
    status: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(100))
    turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    started_by: Mapped[int] = _fk("users.id", cascade=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    official: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint(
            "kind", "nazwa_klauzuli", "wersja", name="uq_templates_kind_klauzula_wersja"
        ),
        _in("kind", CONTRACT_KINDS, "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    nazwa_klauzuli: Mapped[str] = mapped_column(String(200))
    tresc: Mapped[str] = mapped_column(Text)
    wersja: Mapped[int] = mapped_column(Integer)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        _in("typ", FINDING_TYPES, "typ"),
        _in("poziom_ryzyka", RISK_LEVELS, "poziom_ryzyka", nullable=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = _fk("analyses.id")
    typ: Mapped[str] = mapped_column(String(20))
    teza: Mapped[str] = mapped_column(Text)
    cytat: Mapped[str] = mapped_column(Text)
    fragment_id: Mapped[str] = mapped_column(String(MAX_FRAGMENT_ID_LEN))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    poziom_ryzyka: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uzasadnienie: Mapped[str] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )


class RejectedClaim(Base):
    __tablename__ = "rejected_claims"
    __table_args__ = (
        _in("typ", FINDING_TYPES, "typ"),
        _in("poziom_ryzyka", RISK_LEVELS, "poziom_ryzyka", nullable=True),
        _in("powod", REJECT_REASONS, "powod"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = _fk("analyses.id")
    typ: Mapped[str] = mapped_column(String(20))
    teza: Mapped[str] = mapped_column(Text)
    cytat: Mapped[str] = mapped_column(Text)
    fragment_id: Mapped[str] = mapped_column(String(MAX_FRAGMENT_ID_LEN))
    poziom_ryzyka: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uzasadnienie: Mapped[str] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )
    powod: Mapped[str] = mapped_column(String(40))


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_a: Mapped[int] = _fk("contract_versions.id")
    version_b: Mapped[int] = _fk("contract_versions.id")
    fragment_changes: Mapped[Any] = mapped_column(JSONB)
    finding_changes: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = _created()


class PendingAction(Base):
    __tablename__ = "pending_actions"
    __table_args__ = (
        _in("typ", ACTION_TYPES, "typ"),
        _in("status", ACTION_STATUSES, "status"),
        Index(
            "uq_pending_actions_open",
            "analysis_id",
            "typ",
            unique=True,
            postgresql_where=text("status = 'oczekuje'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    typ: Mapped[str] = mapped_column(String(20))
    analysis_id: Mapped[int] = _fk("analyses.id")
    payload: Mapped[Any] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), default="oczekuje", server_default="oczekuje")
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    akcja: Mapped[str] = mapped_column(String(100))
    obiekt: Mapped[str] = mapped_column(String(200))
    kiedy: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = _fk("users.id")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = _fk("analyses.id")
    action_id: Mapped[int] = _fk("pending_actions.id")
    content: Mapped[Any] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
