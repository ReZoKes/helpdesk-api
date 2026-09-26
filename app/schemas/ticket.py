from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)

from app.models.ticket import TicketPriority, TicketStatus

SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class TicketSort(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"
    PRIORITY = "priority"


class TicketListQuery(BaseModel):
    status: TicketStatus | None = None
    search: SearchQuery | None = None
    sort: TicketSort = TicketSort.NEWEST
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    customer_email: EmailStr
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    customer_email: EmailStr
    status: TicketStatus
    priority: TicketPriority
    allowed_transitions: list[TicketStatus]
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int


class TicketStats(BaseModel):
    total: int
    new: int
    in_progress: int
    closed: int


class TicketEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    old_status: TicketStatus | None
    new_status: TicketStatus
    created_at: datetime
