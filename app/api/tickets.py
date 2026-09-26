from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import TicketServiceDep
from app.models.ticket import TicketStatus
from app.schemas.ticket import (
    TicketCreate,
    TicketEventRead,
    TicketListQuery,
    TicketListResponse,
    TicketRead,
    TicketStats,
    TicketStatusUpdate,
)
from app.services.notification_service import send_status_changed_email

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    data: TicketCreate,
    service: TicketServiceDep,
) -> TicketRead:
    ticket = await service.create(data)
    return TicketRead.model_validate(ticket)


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    params: Annotated[TicketListQuery, Query()],
    service: TicketServiceDep,
) -> TicketListResponse:
    items, total = await service.get_list(params)
    return TicketListResponse(
        items=[TicketRead.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/stats", response_model=TicketStats)
async def get_ticket_stats(service: TicketServiceDep) -> TicketStats:
    stats = await service.get_stats()
    return TicketStats(
        total=sum(stats.values()),
        new=stats[TicketStatus.NEW],
        in_progress=stats[TicketStatus.IN_PROGRESS],
        closed=stats[TicketStatus.CLOSED],
    )


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(
    ticket_id: int,
    service: TicketServiceDep,
) -> TicketRead:
    ticket = await service.get(ticket_id)
    return TicketRead.model_validate(ticket)


@router.get(
    "/{ticket_id}/events",
    response_model=list[TicketEventRead],
)
async def get_ticket_events(
    ticket_id: int,
    service: TicketServiceDep,
) -> list[TicketEventRead]:
    events = await service.get_events(ticket_id)
    return [TicketEventRead.model_validate(event) for event in events]


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketRead,
    responses={409: {"description": "Status transition is not allowed"}},
)
async def update_ticket_status(
    ticket_id: int,
    data: TicketStatusUpdate,
    service: TicketServiceDep,
    background_tasks: BackgroundTasks,
) -> TicketRead:
    ticket, old_status = await service.update_status(ticket_id, data.status)
    if old_status != ticket.status:
        background_tasks.add_task(
            send_status_changed_email,
            email=ticket.customer_email,
            ticket_id=ticket.id,
            ticket_title=ticket.title,
            old_status=old_status,
            new_status=ticket.status,
        )
    return TicketRead.model_validate(ticket)


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ticket(
    ticket_id: int,
    service: TicketServiceDep,
) -> None:
    await service.delete(ticket_id)
