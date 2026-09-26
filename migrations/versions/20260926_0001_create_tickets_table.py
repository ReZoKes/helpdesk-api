"""create tickets table

Revision ID: 0001
Revises:
Create Date: 2026-09-26 18:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ticket_status = sa.Enum(
    "new", "in_progress", "closed", name="ticket_status"
)
ticket_priority = sa.Enum(
    "low", "medium", "high", "critical", name="ticket_priority"
)


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("customer_email", sa.String(length=320), nullable=False),
        sa.Column(
            "status",
            ticket_status,
            server_default="new",
            nullable=False,
        ),
        sa.Column(
            "priority",
            ticket_priority,
            server_default="medium",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index(
        op.f("ix_tickets_status"), "tickets", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_tickets_created_at"),
        "tickets",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tickets_created_at"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_status"), table_name="tickets")
    op.drop_table("tickets")
    ticket_priority.drop(op.get_bind(), checkfirst=True)
    ticket_status.drop(op.get_bind(), checkfirst=True)
