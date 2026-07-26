from __future__ import annotations

import asyncio
import logging

import httpx
from datetime import datetime, timezone
from sqlalchemy import select

from app.settings import Settings

from .client import TelegramClient
from .commands import BOT_COMMANDS, CommandResponse, CommandRouter
from .alerts import event_matches, setup_event_matches_default
from app.telemetry.models import (AlertSubscriptionRecord,
                                  IndicatorAlertEventRecord,
                                  WatchlistAssetRecord)
from app.telemetry.repository import record_heartbeat

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, settings: Settings, client: TelegramClient, router: CommandRouter):
        if settings.telegram_chat_id is None:
            raise ValueError("TELEGRAM_CHAT_ID is missing")
        if not settings.allowed_users:
            raise ValueError("PLATFORM_TELEGRAM_ALLOWED_USER_IDS is empty")
        self.settings, self.client, self.router = settings, client, router
        self.offset: int | None = None

    async def process_update(self, update: dict) -> bool:
        callback = update.get("callback_query")
        if callback:
            return await self.process_callback(callback)
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        user_id = (message.get("from") or {}).get("id")
        text = message.get("text", "")
        if chat_id != self.settings.telegram_chat_id:
            logger.warning("Rejected Telegram message from unauthorized chat_id=%s", chat_id)
            return False
        if user_id not in self.settings.allowed_users:
            logger.warning("Rejected Telegram command from unauthorized user_id=%s", user_id)
            await self.client.send(chat_id, "Unauthorized user.")
            return False
        if not text.startswith("/"):
            return False
        response = self.router.dispatch(text, user_id)
        await self.send_response(chat_id, response)
        return True

    async def process_callback(self, callback: dict) -> bool:
        message = callback.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        user_id = (callback.get("from") or {}).get("id")
        callback_id = callback.get("id")
        if chat_id != self.settings.telegram_chat_id or user_id not in self.settings.allowed_users:
            logger.warning("Rejected Telegram callback chat_id=%s user_id=%s", chat_id, user_id)
            if callback_id:
                await self.client.answer_callback(callback_id, "Unauthorized")
            return False
        try:
            response = self.router.dispatch_callback(callback.get("data", ""), user_id)
            if callback_id:
                await self.client.answer_callback(callback_id)
            await self.send_response(chat_id, response)
            return True
        except (ValueError, TypeError) as error:
            if callback_id:
                await self.client.answer_callback(callback_id, "Action rejected")
            await self.client.send(chat_id, f"Menu action rejected: {error}")
            return False

    async def send_response(self, chat_id: int, response: str | CommandResponse) -> None:
        if isinstance(response, CommandResponse):
            await self.client.send(chat_id, response.text, response.reply_markup)
        else:
            await self.client.send(chat_id, response)

    async def run_forever(self):
        identity = await self.client.identity()
        await self.client.set_commands(BOT_COMMANDS)
        logger.info("Telegram bot connected username=%s", identity.get("username"))
        while True:
            try:
                with self.router.session_factory() as session:
                    record_heartbeat(session, "telegram-bot", self.settings.strategy_version,
                                     self.settings.git_sha)
                await self.drain_alerts()
                updates = await self.client.updates(self.offset)
                for update in updates:
                    self.offset = int(update["update_id"]) + 1
                    await self.process_update(update)
            except httpx.ReadTimeout:
                logger.warning("Telegram long poll timed out; retrying")
                await asyncio.sleep(1)
            except (httpx.HTTPError, OSError) as error:
                # Exception strings may include the credential-bearing request URL.
                logger.error("Telegram polling error type=%s", type(error).__name__)
                await asyncio.sleep(5)

    async def drain_alerts(self) -> int:
        sent = 0
        with self.router.session_factory() as session:
            events = list(session.scalars(select(IndicatorAlertEventRecord).where(
                IndicatorAlertEventRecord.delivered_at.is_(None)
            ).order_by(IndicatorAlertEventRecord.created_at).limit(50)))
            subscriptions = list(session.scalars(select(AlertSubscriptionRecord).where(
                AlertSubscriptionRecord.chat_id == str(self.settings.telegram_chat_id))))
            tracked = set(session.scalars(select(WatchlistAssetRecord.symbol).where(
                WatchlistAssetRecord.status.in_(["active", "probe"]))))
            for event in events:
                matching = [item for item in subscriptions if event_matches(event, item)]
                default_setup = setup_event_matches_default(event, subscriptions,
                                                            event.symbol in tracked)
                if matching or default_setup:
                    label = "Setup alert" if event.event_type == "setup_transition" else "Indicator alert"
                    await self.client.send(self.settings.telegram_chat_id, label + ":\n" + event.message)
                    sent += 1
                event.delivered_at = datetime.now(timezone.utc)
                session.commit()
        return sent
