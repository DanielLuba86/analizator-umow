"""schemat

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("nazwa_klauzuli", sa.String(length=200), nullable=False),
        sa.Column("tresc", sa.Text(), nullable=False),
        sa.Column("wersja", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('najem', 'dostawa', 'zlecenie')", name=op.f("ck_templates_kind")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_templates")),
        sa.UniqueConstraint(
            "kind", "nazwa_klauzuli", "wersja", name=op.f("uq_templates_kind_klauzula_wersja")
        ),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.CheckConstraint("role IN ('asystent', 'prawnik')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("login", name=op.f("uq_users_login")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("akcja", sa.String(length=100), nullable=False),
        sa.Column("obiekt", sa.String(length=200), nullable=False),
        sa.Column(
            "kiedy", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('najem', 'dostawa', 'zlecenie')", name=op.f("ck_contracts_kind")
        ),
        sa.CheckConstraint(
            "source IN ('wewnętrzna', 'kontrahent')", name=op.f("ck_contracts_source")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_contracts_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contracts")),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
    )
    op.create_table(
        "contract_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("nr", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name=op.f("fk_contract_versions_contract_id_contracts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_versions")),
        sa.UniqueConstraint("contract_id", "nr", name=op.f("uq_contract_versions_contract_id_nr")),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("turns", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("started_by", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("official", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed', 'quarantined', 'budget_exceeded')",
            name=op.f("ck_analyses_status"),
        ),
        sa.ForeignKeyConstraint(
            ["started_by"], ["users.id"], name=op.f("fk_analyses_started_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["contract_versions.id"],
            name=op.f("fk_analyses_version_id_contract_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyses")),
    )
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_a", sa.Integer(), nullable=False),
        sa.Column("version_b", sa.Integer(), nullable=False),
        sa.Column("fragment_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("finding_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["version_a"],
            ["contract_versions.id"],
            name=op.f("fk_comparisons_version_a_contract_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_b"],
            ["contract_versions.id"],
            name=op.f("fk_comparisons_version_b_contract_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comparisons")),
    )
    op.create_table(
        "fragments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("frag_id", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["contract_versions.id"],
            name=op.f("fk_fragments_version_id_contract_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fragments")),
        sa.UniqueConstraint("version_id", "frag_id", name=op.f("uq_fragments_version_id_frag_id")),
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("typ", sa.String(length=20), nullable=False),
        sa.Column("teza", sa.Text(), nullable=False),
        sa.Column("cytat", sa.Text(), nullable=False),
        sa.Column("fragment_id", sa.String(length=20), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("poziom_ryzyka", sa.String(length=20), nullable=True),
        sa.Column("uzasadnienie", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "poziom_ryzyka IS NULL OR poziom_ryzyka IN ('niskie', 'średnie', 'wysokie')",
            name=op.f("ck_findings_poziom_ryzyka"),
        ),
        sa.CheckConstraint(
            "typ IN ('strona', 'termin', 'kara', 'ryzyko', 'wstrzyknięcie')",
            name=op.f("ck_findings_typ"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name=op.f("fk_findings_analysis_id_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["templates.id"],
            name=op.f("fk_findings_template_id_templates"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
    )
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("typ", sa.String(length=20), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="oczekuje", nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('oczekuje', 'zatwierdzona', 'odrzucona')",
            name=op.f("ck_pending_actions_status"),
        ),
        sa.CheckConstraint(
            "typ IN ('opinia', 'wzorzec', 'eksport', 'kwarantanna')",
            name=op.f("ck_pending_actions_typ"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name=op.f("fk_pending_actions_analysis_id_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name=op.f("fk_pending_actions_decided_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_actions")),
    )
    op.create_index(
        "uq_pending_actions_open",
        "pending_actions",
        ["analysis_id", "typ"],
        unique=True,
        postgresql_where=sa.text("status = 'oczekuje'"),
    )
    op.create_table(
        "rejected_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("typ", sa.String(length=20), nullable=False),
        sa.Column("teza", sa.Text(), nullable=False),
        sa.Column("cytat", sa.Text(), nullable=False),
        sa.Column("fragment_id", sa.String(length=20), nullable=False),
        sa.Column("poziom_ryzyka", sa.String(length=20), nullable=True),
        sa.Column("uzasadnienie", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("powod", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "powod IN ('brak_dosłownego_cytatu', 'zły_fragment', 'za_krótki_cytat', 'limit_tez')",
            name=op.f("ck_rejected_claims_powod"),
        ),
        sa.CheckConstraint(
            "poziom_ryzyka IS NULL OR poziom_ryzyka IN ('niskie', 'średnie', 'wysokie')",
            name=op.f("ck_rejected_claims_poziom_ryzyka"),
        ),
        sa.CheckConstraint(
            "typ IN ('strona', 'termin', 'kara', 'ryzyko', 'wstrzyknięcie')",
            name=op.f("ck_rejected_claims_typ"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name=op.f("fk_rejected_claims_analysis_id_analyses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["templates.id"],
            name=op.f("fk_rejected_claims_template_id_templates"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rejected_claims")),
    )
    op.create_table(
        "exports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["pending_actions.id"],
            name=op.f("fk_exports_action_id_pending_actions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            name=op.f("fk_exports_analysis_id_analyses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exports")),
    )


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("rejected_claims")
    op.drop_index(
        "uq_pending_actions_open",
        table_name="pending_actions",
        postgresql_where=sa.text("status = 'oczekuje'"),
    )
    op.drop_table("pending_actions")
    op.drop_table("findings")
    op.drop_table("fragments")
    op.drop_table("comparisons")
    op.drop_table("analyses")
    op.drop_table("contract_versions")
    op.drop_table("sessions")
    op.drop_table("contracts")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("templates")
