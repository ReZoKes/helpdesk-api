from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

API = "/api/v1/tickets"


async def create_ticket(
    client: AsyncClient,
    title: str,
    description: str = "Description",
    priority: str = "medium",
) -> dict[str, Any]:
    response = await client.post(
        API,
        json={
            "title": title,
            "description": description,
            "customer_email": "user@example.com",
            "priority": priority,
        },
    )
    assert response.status_code == 201
    return response.json()


async def set_status(
    client: AsyncClient, ticket_id: int, status: str
) -> None:
    response = await client.patch(
        f"{API}/{ticket_id}/status", json={"status": status}
    )
    assert response.status_code == 200


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_create_ticket(
    client: AsyncClient,
    ticket_payload: dict[str, Any],
) -> None:
    response = await client.post(API, json=ticket_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == ticket_payload["title"]
    assert body["status"] == "new"
    assert body["priority"] == "high"
    assert body["allowed_transitions"] == ["in_progress", "closed"]


async def test_create_ticket_default_priority(client: AsyncClient) -> None:
    body = await create_ticket(client, "Printer jam")

    assert body["priority"] == "medium"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "ab"),
        ("title", "x" * 201),
        ("description", ""),
        ("customer_email", "not-an-email"),
        ("priority", "urgent"),
    ],
)
async def test_create_ticket_validation_error(
    client: AsyncClient,
    ticket_payload: dict[str, Any],
    field: str,
    value: str,
) -> None:
    response = await client.post(API, json={**ticket_payload, field: value})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]


async def test_get_ticket(
    client: AsyncClient,
    created_ticket: dict[str, Any],
) -> None:
    response = await client.get(f"{API}/{created_ticket['id']}")

    assert response.status_code == 200
    assert response.json() == created_ticket


async def test_get_ticket_not_found(client: AsyncClient) -> None:
    response = await client.get(f"{API}/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Ticket 999 not found"}


async def test_list_tickets_pagination(client: AsyncClient) -> None:
    for number in range(1, 6):
        await create_ticket(client, f"Ticket {number}")

    response = await client.get(API, params={"limit": 2, "offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert [item["title"] for item in body["items"]] == [
        "Ticket 3",
        "Ticket 2",
    ]


async def test_list_tickets_filter_by_status(client: AsyncClient) -> None:
    first = await create_ticket(client, "First")
    await create_ticket(client, "Second")
    await set_status(client, first["id"], "in_progress")

    response = await client.get(API, params={"status": "in_progress"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == first["id"]


@pytest.mark.parametrize(
    ("search", "expected_titles"),
    [
        ("vpn", ["VPN is down"]),
        ("PRINTER", ["Printer jam"]),
        ("mail", ["Mail server"]),
        ("  jam  ", ["Printer jam"]),
        ("nothing", []),
    ],
)
async def test_list_tickets_search(
    client: AsyncClient,
    search: str,
    expected_titles: list[str],
) -> None:
    await create_ticket(client, "VPN is down")
    await create_ticket(client, "Printer jam")
    await create_ticket(client, "Mail server", description="No mail today")

    response = await client.get(API, params={"search": search})

    body = response.json()
    assert [item["title"] for item in body["items"]] == expected_titles
    assert body["total"] == len(expected_titles)


async def test_list_tickets_search_escapes_like_wildcards(
    client: AsyncClient,
) -> None:
    await create_ticket(client, "Disk is 100% full")
    await create_ticket(client, "Disk is 100 GB")

    response = await client.get(API, params={"search": "100%"})

    assert [item["title"] for item in response.json()["items"]] == [
        "Disk is 100% full"
    ]


async def test_list_tickets_search_combined_with_status(
    client: AsyncClient,
) -> None:
    first = await create_ticket(client, "VPN office")
    await create_ticket(client, "VPN home")
    await set_status(client, first["id"], "closed")

    response = await client.get(
        API, params={"search": "vpn", "status": "closed"}
    )

    assert [item["id"] for item in response.json()["items"]] == [first["id"]]


@pytest.mark.parametrize(
    ("sort", "expected_titles"),
    [
        ("newest", ["Critical", "Low", "High"]),
        ("oldest", ["High", "Low", "Critical"]),
        ("priority", ["Critical", "High", "Low"]),
    ],
)
async def test_list_tickets_sort(
    client: AsyncClient,
    sort: str,
    expected_titles: list[str],
) -> None:
    await create_ticket(client, "High", priority="high")
    await create_ticket(client, "Low", priority="low")
    await create_ticket(client, "Critical", priority="critical")

    response = await client.get(API, params={"sort": sort})

    assert [
        item["title"] for item in response.json()["items"]
    ] == expected_titles


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"status": "unknown"},
        {"sort": "random"},
        {"search": "   "},
        {"search": "x" * 101},
    ],
)
async def test_list_tickets_invalid_params(
    client: AsyncClient,
    params: dict[str, Any],
) -> None:
    response = await client.get(API, params=params)

    assert response.status_code == 422


async def test_stats(client: AsyncClient) -> None:
    first = await create_ticket(client, "First")
    second = await create_ticket(client, "Second")
    await create_ticket(client, "Third")
    await set_status(client, first["id"], "in_progress")
    await set_status(client, second["id"], "closed")

    response = await client.get(f"{API}/stats")

    assert response.json() == {
        "total": 3,
        "new": 1,
        "in_progress": 1,
        "closed": 1,
    }


async def test_update_status_schedules_email(
    client: AsyncClient,
    created_ticket: dict[str, Any],
    email_mock: AsyncMock,
) -> None:
    response = await client.patch(
        f"{API}/{created_ticket['id']}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["allowed_transitions"] == ["new", "closed"]
    email_mock.assert_called_once_with(
        email=created_ticket["customer_email"],
        ticket_id=created_ticket["id"],
        ticket_title=created_ticket["title"],
        old_status="new",
        new_status="in_progress",
    )


async def test_update_to_same_status_does_not_send_email(
    client: AsyncClient,
    created_ticket: dict[str, Any],
    email_mock: AsyncMock,
) -> None:
    response = await client.patch(
        f"{API}/{created_ticket['id']}/status", json={"status": "new"}
    )

    assert response.status_code == 200
    email_mock.assert_not_called()


async def test_invalid_status_transition_returns_409(
    client: AsyncClient,
    created_ticket: dict[str, Any],
    email_mock: AsyncMock,
) -> None:
    await set_status(client, created_ticket["id"], "closed")

    response = await client.patch(
        f"{API}/{created_ticket['id']}/status", json={"status": "new"}
    )

    assert response.status_code == 409
    assert "not allowed" in response.json()["detail"]
    assert email_mock.call_count == 1


async def test_update_status_not_found(client: AsyncClient) -> None:
    response = await client.patch(
        f"{API}/999/status", json={"status": "closed"}
    )

    assert response.status_code == 404


async def test_ticket_events_history(
    client: AsyncClient,
    created_ticket: dict[str, Any],
    email_mock: AsyncMock,
) -> None:
    ticket_id = created_ticket["id"]
    await set_status(client, ticket_id, "in_progress")
    await set_status(client, ticket_id, "closed")

    response = await client.get(f"{API}/{ticket_id}/events")

    assert response.status_code == 200
    transitions = [
        (event["old_status"], event["new_status"])
        for event in response.json()
    ]
    assert transitions == [
        (None, "new"),
        ("new", "in_progress"),
        ("in_progress", "closed"),
    ]


async def test_delete_ticket(
    client: AsyncClient,
    created_ticket: dict[str, Any],
) -> None:
    ticket_id = created_ticket["id"]

    response = await client.delete(f"{API}/{ticket_id}")

    assert response.status_code == 204
    assert (await client.get(f"{API}/{ticket_id}")).status_code == 404
    events = await client.get(f"{API}/{ticket_id}/events")
    assert events.status_code == 404


async def test_delete_ticket_not_found(client: AsyncClient) -> None:
    response = await client.delete(f"{API}/999")

    assert response.status_code == 404
