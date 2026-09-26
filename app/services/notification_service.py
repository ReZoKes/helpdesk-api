import asyncio
import logging

from app.models.ticket import TicketStatus

logger = logging.getLogger(__name__)

EMAIL_SEND_DELAY_SECONDS = 2


async def send_status_changed_email(
    email: str,
    ticket_id: int,
    ticket_title: str,
    old_status: TicketStatus,
    new_status: TicketStatus,
) -> None:
    logger.info(
        "Sending email to %s: ticket #%d '%s' status %s -> %s",
        email,
        ticket_id,
        ticket_title,
        old_status.value,
        new_status.value,
    )
    await asyncio.sleep(EMAIL_SEND_DELAY_SECONDS)
    logger.info("Email for ticket #%d sent to %s", ticket_id, email)
