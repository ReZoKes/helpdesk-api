from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.ticket import TicketStatus, ticket_status_enum

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class TicketEvent(Base):
    """Audit record of a ticket status change.

    ``old_status`` is ``None`` for the event of ticket creation.
    """

    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        index=True,
    )
    old_status: Mapped[TicketStatus | None] = mapped_column(
        ticket_status_enum
    )
    new_status: Mapped[TicketStatus] = mapped_column(ticket_status_enum)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<TicketEvent ticket_id={self.ticket_id} "
            f"{self.old_status} -> {self.new_status}>"
        )
