"""create ticket_events table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26 18:40:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ticket_status = postgresql.ENUM(
    "new",
    "in_progress",
    "closed",
    name="ticket_status",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("old_status", ticket_status, nullable=True),
        sa.Column("new_status", ticket_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name=op.f("fk_ticket_events_ticket_id_tickets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_events")),
    )
    op.create_index(
        op.f("ix_ticket_events_ticket_id"),
        "ticket_events",
        ["ticket_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO ticket_events (ticket_id, old_status, new_status,
                                   created_at)
        SELECT id, NULL, status, created_at FROM tickets
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ticket_events_ticket_id"), table_name="ticket_events"
    )
    op.drop_table("ticket_events")
