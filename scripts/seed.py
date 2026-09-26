"""Fill the database with demo tickets.

Usage: python -m scripts.seed
"""

import asyncio

from app.core.database import async_session_factory, engine
from app.models.ticket import TicketPriority, TicketStatus
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import TicketService

type DemoTicket = tuple[str, str, str, TicketPriority, list[TicketStatus]]

DEMO_TICKETS: list[DemoTicket] = [
    (
        "Не работает VPN после обновления клиента",
        "После обновления Cisco AnyConnect до версии 5.1 соединение "
        "обрывается через 30 секунд. Проблема у всего отдела продаж.",
        "sales@romashka.ru",
        TicketPriority.CRITICAL,
        [TicketStatus.IN_PROGRESS],
    ),
    (
        "Упал сервер 1С в филиале Казани",
        "С 9:00 недоступна база 1С:Бухгалтерия, при подключении "
        "ошибка «Сервер 1С:Предприятия не обнаружен».",
        "it@kazan.romashka.ru",
        TicketPriority.CRITICAL,
        [],
    ),
    (
        "Заменить картридж в принтере на 3 этаже",
        "HP LaserJet M404 печатает с полосами, картридж на исходе.",
        "office@romashka.ru",
        TicketPriority.LOW,
        [TicketStatus.IN_PROGRESS, TicketStatus.CLOSED],
    ),
    (
        "Выдать доступ к папке «Финансы» новому сотруднику",
        "Новый сотрудник Петров А. С. (бухгалтерия), нужен доступ "
        "на чтение и запись к \\\\fs01\\finance.",
        "hr@romashka.ru",
        TicketPriority.MEDIUM,
        [],
    ),
    (
        "Медленно работает Wi-Fi в переговорной",
        "В переговорной «Нева» видеозвонки в Zoom постоянно зависают, "
        "скорость около 2 Мбит/с.",
        "admin@romashka.ru",
        TicketPriority.HIGH,
        [TicketStatus.IN_PROGRESS],
    ),
    (
        "Не приходят письма с внешних доменов",
        "С утра на корпоративную почту не приходят письма от "
        "контрагентов. Внутренняя переписка работает.",
        "director@romashka.ru",
        TicketPriority.HIGH,
        [],
    ),
    (
        "Установить Visual Studio Code разработчику",
        "Для нового разработчика нужен VS Code и расширения Python.",
        "dev-lead@romashka.ru",
        TicketPriority.LOW,
        [TicketStatus.CLOSED],
    ),
    (
        "Истекает SSL-сертификат на портале клиентов",
        "Сертификат для portal.romashka.ru истекает через 5 дней, "
        "нужно продлить и установить.",
        "security@romashka.ru",
        TicketPriority.HIGH,
        [
            TicketStatus.IN_PROGRESS,
            TicketStatus.CLOSED,
            TicketStatus.IN_PROGRESS,
        ],
    ),
    (
        "Сбросить пароль к учётной записи домена",
        "Сотрудник забыл пароль после отпуска, учётная запись "
        "заблокирована.",
        "ivanova@romashka.ru",
        TicketPriority.MEDIUM,
        [TicketStatus.IN_PROGRESS, TicketStatus.CLOSED],
    ),
    (
        "Настроить резервное копирование базы CRM",
        "Нужно настроить ежедневный бэкап PostgreSQL базы CRM "
        "с хранением 14 дней.",
        "cto@romashka.ru",
        TicketPriority.MEDIUM,
        [],
    ),
]


async def seed() -> None:
    async with async_session_factory() as session:
        service = TicketService(session)
        for title, description, email, priority, statuses in DEMO_TICKETS:
            ticket = await service.create(
                TicketCreate(
                    title=title,
                    description=description,
                    customer_email=email,
                    priority=priority,
                )
            )
            for status in statuses:
                await service.update_status(ticket.id, status)
    await engine.dispose()
    print(f"Created {len(DEMO_TICKETS)} demo tickets")


if __name__ == "__main__":
    asyncio.run(seed())
