from __future__ import annotations

from typing import Any

import httpx


class TelegramApiError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None):
        if not token or token.startswith("REPLACE_WITH"):
            raise ValueError("TELEGRAM_BOT_TOKEN is missing")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=60, write=10, pool=10))
        self._owns_client = client is None
        self._base_url = f"https://api.telegram.org/bot{token}"

    async def close(self):
        if self._owns_client:
            await self._client.aclose()

    async def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        response = await self._client.post(f"{self._base_url}/{method}", json=payload or {})
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise TelegramApiError(body.get("description", "Telegram API error"))
        return body.get("result")

    async def updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        payload = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return await self.call("getUpdates", payload)

    async def send(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self.call("sendMessage", payload)

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self.call("answerCallbackQuery", payload)

    async def identity(self) -> dict:
        return await self.call("getMe")

    async def set_commands(self, commands: list[dict[str, str]]) -> None:
        await self.call("setMyCommands", {"commands": commands})
