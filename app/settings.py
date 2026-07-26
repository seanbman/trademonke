import hashlib
import json
import os
import subprocess
from decimal import Decimal
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.runtime import normalize_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PLATFORM_", extra="ignore", populate_by_name=True)
    environment: str = "development"
    dry_run: bool = True
    trading_mode: str = "spot"
    database_url: str = Field(
        default="postgresql+psycopg://trading:CHANGE_ME@127.0.0.1:5432/trading_platform",
        validation_alias=AliasChoices("database_url", "DATABASE_URL", "PLATFORM_DATABASE_URL"),
    )
    strategy_version: str = "fvg-pro-elite-python-v0.4.0"
    git_sha: str = Field(
        default="unknown",
        validation_alias=AliasChoices("git_sha", "SOURCE_VERSION", "HEROKU_SLUG_COMMIT", "PLATFORM_GIT_SHA"),
    )
    embed_market_relay: bool = False
    market_stream_enabled: bool = True
    serve_gui: bool = False
    platform_mode: str = Field(default="full", validation_alias=AliasChoices("platform_mode", "MODE"))
    feeder_token: str = ""
    remote_relay_url: str = ""
    relay_cache_hours: int = 24
    telegram_allowed_user_ids: str = ""
    telegram_bot_token: str = Field(default="", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "PLATFORM_TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: int | None = Field(default=None, validation_alias=AliasChoices("TELEGRAM_CHAT_ID", "PLATFORM_TELEGRAM_CHAT_ID"))
    gui_access_token: str = ""
    execution_mode: str = "disabled"
    kill_switch: bool = False
    market_data_exchange: str = "kraken"
    market_data_symbols: str = Field(default="BTC/USDT,ETH/USDT", validation_alias=AliasChoices("PLATFORM_MARKET_DATA_SYMBOLS", "MARKET_DATA_SYMBOLS"))
    market_data_timeframes: str = Field(default="5m,15m,30m,1h,4h,1d", validation_alias=AliasChoices("PLATFORM_MARKET_DATA_TIMEFRAMES", "MARKET_DATA_TIMEFRAMES"))
    market_data_history_days: int = Field(default=365, validation_alias=AliasChoices("PLATFORM_MARKET_DATA_HISTORY_DAYS", "MARKET_DATA_HISTORY_DAYS"))
    market_data_batch_limit: int = 300
    market_data_max_retries: int = 5
    market_data_stale_multiplier: int = 3
    market_stream_url: str = "ws://127.0.0.1:8100"
    market_stream_bind_host: str = "0.0.0.0"
    market_stream_port: int = 8100
    candidate_quote: str = "USDT"
    candidate_min_quote_volume: float = 10_000_000
    candidate_max_spread_bps: float = 30
    setup_detection_min_score: int = 2
    setup_expiry_candles: int = 40
    indicator_base_timeframe: str = "5m"
    indicator_htf_timeframes: str = "15m,30m,1h,4h,1d"
    indicator_ema_length: int = 50
    indicator_structure_lookback: int = 10
    indicator_smt_lookback: int = 10
    indicator_pivot_lookback: int = 30
    indicator_fvg_max_age: int = 40
    liquidity_pivot_left: int = 2
    liquidity_pivot_right: int = 2
    liquidity_cluster_tolerance_bps: Decimal = Decimal("5")
    liquidity_touch_tolerance_bps: Decimal = Decimal("2")
    liquidity_expiry_candles: int = 500
    episode_displacement_body_bps: Decimal = Decimal("20")
    research_account_balance: Decimal = Decimal("1000")
    research_tick_size: Decimal = Decimal("0.1")
    research_slippage_bps: Decimal = Decimal("10")
    risk_fraction: Decimal = Decimal("0.005")
    minimum_risk_reward: Decimal = Decimal("2")
    maximum_notional: Decimal = Decimal("1000")
    minimum_notional: Decimal = Decimal("10")

    @field_validator("database_url", mode="before")
    @classmethod
    def coerce_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value

    @model_validator(mode="after")
    def fail_closed(self):
        if not self.dry_run:
            raise ValueError("MVP safety guard: PLATFORM_DRY_RUN must be true")
        if self.trading_mode != "spot":
            raise ValueError("MVP safety guard: only spot mode is allowed")
        if self.execution_mode not in {"disabled", "shadow", "dry_run"}:
            raise ValueError("execution mode must be disabled, shadow, or dry_run")
        if self.platform_mode not in {"full", "relay"}:
            raise ValueError("platform mode must be full or relay")
        required = {self.indicator_base_timeframe, *self.indicator_htfs}
        missing = required - set(self.market_timeframes)
        if missing:
            raise ValueError("market-data timeframes must include indicator timeframes: " + ", ".join(sorted(missing)))
        for name in ("indicator_ema_length", "indicator_structure_lookback",
                     "indicator_smt_lookback", "indicator_pivot_lookback",
                     "indicator_fvg_max_age", "setup_expiry_candles",
                     "liquidity_pivot_left", "liquidity_pivot_right",
                     "liquidity_expiry_candles"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if self.liquidity_cluster_tolerance_bps < 0 or self.liquidity_touch_tolerance_bps < 0:
            raise ValueError("liquidity tolerances cannot be negative")
        if self.episode_displacement_body_bps <= 0:
            raise ValueError("episode displacement threshold must be positive")
        for name in ("research_account_balance", "research_tick_size", "risk_fraction",
                     "minimum_risk_reward", "maximum_notional", "minimum_notional"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.git_sha == "unknown":
            try:
                resolved = subprocess.run(
                    ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
                    text=True, timeout=2).stdout.strip()
                if resolved:
                    self.git_sha = resolved
            except (OSError, subprocess.SubprocessError):
                pass
        if os.environ.get("DYNO", "").startswith("web."):
            self.serve_gui = True
        return self

    @property
    def config_hash(self) -> str:
        excluded = {"database_url", "telegram_allowed_user_ids", "telegram_bot_token",
                    "telegram_chat_id", "gui_access_token", "git_sha", "market_stream_url",
                    "market_stream_bind_host", "market_stream_port"}
        payload = self.model_dump(exclude=excluded, mode="json")
        return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()

    @property
    def allowed_users(self) -> set[int]:
        return {int(value.strip()) for value in self.telegram_allowed_user_ids.split(",") if value.strip()}

    @property
    def market_symbols(self) -> tuple[str, ...]:
        return tuple(x.strip() for x in self.market_data_symbols.split(",") if x.strip())

    @property
    def market_timeframes(self) -> tuple[str, ...]:
        return tuple(x.strip() for x in self.market_data_timeframes.split(",") if x.strip())

    @property
    def indicator_htfs(self) -> tuple[str, ...]:
        return tuple(x.strip() for x in self.indicator_htf_timeframes.split(",") if x.strip())

    @property
    def is_relay_mode(self) -> bool:
        return self.platform_mode == "relay"


@lru_cache
def get_settings() -> Settings:
    return Settings()
