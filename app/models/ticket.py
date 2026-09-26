from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ticket_event import TicketEvent


class TicketStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


ALLOWED_STATUS_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.NEW: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED}
    ),
    TicketStatus.IN_PROGRESS: frozenset(
        {TicketStatus.NEW, TicketStatus.CLOSED}
    ),
    TicketStatus.CLOSED: frozenset({TicketStatus.IN_PROGRESS}),
}


def is_transition_allowed(
    current: TicketStatus,
    requested: TicketStatus,
) -> bool:
    return requested in ALLOWED_STATUS_TRANSITIONS[current]


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


ticket_status_enum = Enum(
    TicketStatus,
    name="ticket_status",
    values_callable=_enum_values,
)
ticket_priority_enum = Enum(
    TicketPriority,
    name="ticket_priority",
    values_callable=_enum_values,
)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    customer_email: Mapped[str] = mapped_column(String(320))
    status: Mapped[TicketStatus] = mapped_column(
        ticket_status_enum,
        default=TicketStatus.NEW,
        server_default=TicketStatus.NEW.value,
        index=True,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        ticket_priority_enum,
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # lazy="raise": implicit lazy loading is impossible in async mode,
    # so accidental access fails loudly instead of with MissingGreenlet.
    events: Mapped[list["TicketEvent"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    @property
    def allowed_transitions(self) -> list[TicketStatus]:
        return [
            status
            for status in TicketStatus
            if is_transition_allowed(self.status, status)
        ]

    def can_transition_to(self, new_status: TicketStatus) -> bool:
        return is_transition_allowed(self.status, new_status)

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} status={self.status}>"
