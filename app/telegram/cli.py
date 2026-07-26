import asyncio
import logging

from app.settings import get_settings
from app.telemetry.db import SessionLocal
from app.telemetry.logging import configure_json_logging

from .client import TelegramClient
from .commands import CommandRouter
from .service import TelegramService


async def run() -> None:
    settings = get_settings()
    client = TelegramClient(settings.telegram_bot_token)
    service = TelegramService(settings, client, CommandRouter(settings, SessionLocal))
    try:
        await service.run_forever()
    finally:
        await client.close()


def main() -> None:
    configure_json_logging()
    # HTTP request URLs contain the Telegram bot token. Never emit transport logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    asyncio.run(run())


if __name__ == "__main__":
    main()
