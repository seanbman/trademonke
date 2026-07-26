from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, TypeVar

import ccxt.async_support as ccxt

T = TypeVar("T")


class ReadOnlyExchange:
    """Public-only CCXT client. It exposes no order or credential methods."""

    def __init__(self, exchange_id: str, max_retries: int = 5):
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"unsupported CCXT exchange: {exchange_id}")
        self.client = exchange_class({"enableRateLimit": True, "timeout": 30_000})
        self.exchange_id = exchange_id
        self.max_retries = max_retries

    async def __aenter__(self):
        try:
            await self.retry(self.client.load_markets)
        except Exception:
            await self.client.close()
            raise
        return self

    async def __aexit__(self, *_):
        await self.client.close()

    async def retry(self, operation: Callable[[], Awaitable[T]]) -> T:
        for attempt in range(self.max_retries):
            try:
                return await operation()
            except (ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable):
                if attempt + 1 == self.max_retries:
                    raise
                await asyncio.sleep(min(2**attempt, 16) + random.random())
        raise RuntimeError("unreachable retry state")

    def require_spot_symbol(self, symbol: str) -> None:
        market = self.client.markets.get(symbol)
        if not market or not market.get("spot") or not market.get("active", True):
            raise ValueError(f"active spot symbol unavailable on {self.exchange_id}: {symbol}")

    async def fetch_ohlcv(self, symbol: str, timeframe: str, since: int, limit: int) -> list[list[Any]]:
        self.require_spot_symbol(symbol)
        if not self.client.has.get("fetchOHLCV"):
            raise ValueError(f"{self.exchange_id} does not expose fetchOHLCV")
        return await self.retry(lambda: self.client.fetch_ohlcv(symbol, timeframe, since, limit))

    async def fetch_tickers(self) -> dict[str, dict[str, Any]]:
        if not self.client.has.get("fetchTickers"):
            raise ValueError(f"{self.exchange_id} does not expose fetchTickers")
        return await self.retry(self.client.fetch_tickers)

    async def fetch_funding_rate(self, symbol: str):
        if not self.client.has.get("fetchFundingRate"):
            return None
        return await self.retry(lambda: self.client.fetch_funding_rate(symbol))

    async def fetch_open_interest(self, symbol: str):
        if not self.client.has.get("fetchOpenInterest"):
            return None
        return await self.retry(lambda: self.client.fetch_open_interest(symbol))
