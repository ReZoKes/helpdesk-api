from app.models.ticket import TicketStatus


class ServiceError(Exception):
    """Base class for business logic errors."""


class TicketNotFoundError(ServiceError):
    def __init__(self, ticket_id: int) -> None:
        super().__init__(f"Ticket {ticket_id} not found")
        self.ticket_id = ticket_id


class InvalidStatusTransitionError(ServiceError):
    def __init__(
        self,
        current: TicketStatus,
        requested: TicketStatus,
    ) -> None:
        super().__init__(
            f"Status transition '{current}' -> '{requested}' is not allowed"
        )
        self.current = current
        self.requested = requested
