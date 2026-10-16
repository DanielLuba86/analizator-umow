"""indeksy kluczy obcych i powód agenta

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FK_COLUMNS = (
    ("analyses", "started_by"),
    ("analyses", "version_id"),
    ("audit_log", "user_id"),
    ("comparisons", "version_a"),
    ("comparisons", "version_b"),
    ("contracts", "created_by"),
    ("exports", "action_id"),
    ("exports", "analysis_id"),
    ("findings", "analysis_id"),
    ("findings", "template_id"),
    ("pending_actions", "analysis_id"),
    ("pending_actions", "decided_by"),
    ("rejected_claims", "analysis_id"),
    ("rejected_claims", "template_id"),
    ("sessions", "user_id"),
)


def upgrade() -> None:
    for table, column in FK_COLUMNS:
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
    op.add_column("analyses", sa.Column("agent_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "agent_reason")
    for table, column in reversed(FK_COLUMNS):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
