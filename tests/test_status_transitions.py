import pytest

from app.models.ticket import TicketStatus, is_transition_allowed

NEW = TicketStatus.NEW
IN_PROGRESS = TicketStatus.IN_PROGRESS
CLOSED = TicketStatus.CLOSED


@pytest.mark.parametrize(
    ("current", "requested", "expected"),
    [
        (NEW, IN_PROGRESS, True),
        (NEW, CLOSED, True),
        (IN_PROGRESS, NEW, True),
        (IN_PROGRESS, CLOSED, True),
        (CLOSED, IN_PROGRESS, True),
        (CLOSED, NEW, False),
        (NEW, NEW, False),
        (CLOSED, CLOSED, False),
    ],
)
def test_is_transition_allowed(
    current: TicketStatus,
    requested: TicketStatus,
    expected: bool,
) -> None:
    assert is_transition_allowed(current, requested) is expected
