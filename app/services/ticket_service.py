from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_event import TicketEvent
from app.schemas.ticket import TicketCreate, TicketListQuery, TicketSort
from app.services.exceptions import (
    InvalidStatusTransitionError,
    TicketNotFoundError,
)

# PostgreSQL orders ENUM values by declaration order (low ... critical),
# so DESC puts critical tickets first.
SORT_ORDER: dict[TicketSort, tuple[ColumnElement, ...]] = {
    TicketSort.NEWEST: (Ticket.created_at.desc(), Ticket.id.desc()),
    TicketSort.OLDEST: (Ticket.created_at.asc(), Ticket.id.asc()),
    TicketSort.PRIORITY: (
        Ticket.priority.desc(),
        Ticket.created_at.desc(),
        Ticket.id.desc(),
    ),
}


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TicketCreate) -> Ticket:
        ticket = Ticket(**data.model_dump(), status=TicketStatus.NEW)
        self._session.add(ticket)
        await self._session.flush()
        self._session.add(
            TicketEvent(
                ticket_id=ticket.id,
                old_status=None,
                new_status=ticket.status,
            )
        )
        await self._session.commit()
        await self._session.refresh(ticket)
        return ticket

    async def get(
        self,
        ticket_id: int,
        *,
        for_update: bool = False,
    ) -> Ticket:
        ticket = await self._session.get(
            Ticket, ticket_id, with_for_update=for_update
        )
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        return ticket

    async def get_list(
        self,
        params: TicketListQuery,
    ) -> tuple[Sequence[Ticket], int]:
        conditions: list[ColumnElement[bool]] = []
        if params.status is not None:
            conditions.append(Ticket.status == params.status)
        if params.search is not None:
            pattern = f"%{_escape_like(params.search)}%"
            conditions.append(
                or_(
                    Ticket.title.ilike(pattern, escape="\\"),
                    Ticket.description.ilike(pattern, escape="\\"),
                )
            )

        count_query = select(func.count()).select_from(Ticket)
        query = (
            select(Ticket)
            .where(*conditions)
            .order_by(*SORT_ORDER[params.sort])
            .limit(params.limit)
            .offset(params.offset)
        )

        total = await self._session.scalar(count_query.where(*conditions))
        result = await self._session.scalars(query)
        return result.all(), total or 0

    async def get_stats(self) -> dict[TicketStatus, int]:
        result = await self._session.execute(
            select(Ticket.status, func.count()).group_by(Ticket.status)
        )
        stats = dict.fromkeys(TicketStatus, 0)
        stats.update({status: count for status, count in result.all()})
        return stats

    async def update_status(
        self,
        ticket_id: int,
        new_status: TicketStatus,
    ) -> tuple[Ticket, TicketStatus]:
        ticket = await self.get(ticket_id, for_update=True)
        old_status = ticket.status
        if old_status == new_status:
            return ticket, old_status
        if not ticket.can_transition_to(new_status):
            raise InvalidStatusTransitionError(old_status, new_status)

        ticket.status = new_status
        self._session.add(
            TicketEvent(
                ticket_id=ticket.id,
                old_status=old_status,
                new_status=new_status,
            )
        )
        await self._session.commit()
        await self._session.refresh(ticket)
        return ticket, old_status

    async def get_events(self, ticket_id: int) -> Sequence[TicketEvent]:
        await self.get(ticket_id)
        result = await self._session.scalars(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at, TicketEvent.id)
        )
        return result.all()

    async def delete(self, ticket_id: int) -> None:
        ticket = await self.get(ticket_id)
        await self._session.delete(ticket)
        await self._session.commit()
