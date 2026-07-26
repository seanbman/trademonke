from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    dry_run: bool
    trading_mode: str
    kill_switch: bool
    paused: bool
    database: str
    feed_status: str
    stale_streams: int
    total_streams: int
    services: dict[str, str]
    strategy_version: str
    git_sha: str


class SetupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    pair: str
    timeframe: str
    direction: str
    state: str
    highest_state_reached: str
    components: dict[str, Any]
    detected_at: datetime
    strategy_version: str
    config_hash: str
    git_sha: str


class CollectionResponse(BaseModel):
    items: list[dict[str, Any]]
    count: int


class MarketDataStatus(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    latest_closed_candle: datetime
    age_seconds: float
    stale: bool


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: str
    event_type: str
    sequence: int | None
    schema_version: str
    correlation_id: str
    causation_id: str | None
    occurred_at: datetime
    recorded_at: datetime
    candle_timestamp: datetime | None
    service: str
    environment: str
    market_context: dict[str, Any]
    decision_context: dict[str, Any]
    measurements: dict[str, Any]
    severity: str
    strategy_version: str
    config_hash: str
    git_sha: str


class LiquidityLevelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    exchange: str
    symbol: str
    timeframe: str
    direction: str
    level_type: str
    price: Decimal
    status: str
    observed_at: datetime
    updated_at: datetime
    measurements: dict[str, Any]


class EpisodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    liquidity_level_id: str
    exchange: str
    symbol: str
    timeframe: str
    direction: str
    current_state: str
    highest_state_reached: str
    started_at: datetime
    updated_at: datetime
    terminal_reason: str | None
    current_gate_snapshot: dict[str, Any]


class EpisodeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: str
    episode_id: str
    event_type: str
    prior_state: str | None
    current_state: str
    occurred_at: datetime
    candle_timestamp: datetime
    reason_codes: list[str]
    measurements: dict[str, Any]


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    episode_id: str
    setup_id: str | None
    recommendation_type: str
    version: int
    status: str
    geometry: dict[str, Any]
    source_rules: list[Any]
    source_object_ids: list[Any]
    valid_from: datetime
    valid_until: datetime | None
    supersedes_id: str | None
    created_at: datetime
    strategy_version: str
    config_hash: str
    git_sha: str


class IndicatorSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    direction: str
    score: int
    setup_state: str
    candle_timestamp: datetime
    components: dict[str, Any]


class GuiBootstrapResponse(BaseModel):
    contract_version: str
    generated_at: datetime
    watchlist: list[dict[str, Any]]
    setups: list[SetupResponse]
    episodes: list[EpisodeResponse]
    recommendations: list[RecommendationResponse]
    controls: dict[str, bool]


class ChartDataResponse(BaseModel):
    contract_version: str
    exchange: str
    symbol: str
    timeframe: str
    candles: list[dict[str, Any]]
    liquidity_levels: list[LiquidityLevelResponse]
    imbalances: list[dict[str, Any]]
    episodes: list[EpisodeResponse]
    recommendations: list[RecommendationResponse]
    indicator_snapshots: list[IndicatorSnapshotResponse]
    patterns: list[dict[str, Any]] = []


class AlertAcknowledgementRequest(BaseModel):
    user_id: str
    note: str | None = None
    snoozed_until: datetime | None = None


class AlertAcknowledgementResponse(BaseModel):
    alert_event_id: str
    user_id: str
    acknowledged_at: datetime
    snoozed_until: datetime | None


class ShadowReconciliationRequest(BaseModel):
    user_id: str
    would_fill: bool
    slippage_bps: Decimal
    observed_price: Decimal | None = None


class SymbolSearchHitResponse(BaseModel):
    symbol: str
    base: str
    quote: str
    active: bool
    on_watchlist: bool
    watchlist_status: str | None = None
    protected: bool = False
    quote_volume: float | None = None
    spread_bps: float | None = None
    recommendation: str | None = None
    source: str
    display_name: str = ""
    subtitle: str = ""
    last_price: str | None = None
    price_kind: str | None = None


class SymbolSearchResponse(BaseModel):
    query: str
    exchange: str
    count: int
    items: list[SymbolSearchHitResponse]


class WatchlistChangeRequest(BaseModel):
    symbol: str
    action: str
    user_id: str = "gui-operator"
    reason: str = "GUI watchlist request"


class WatchlistConfirmRequest(BaseModel):
    user_id: str = "gui-operator"


class WatchlistChangeResponse(BaseModel):
    change_id: str
    symbol: str
    target_status: str
    state: str
    expires_at: datetime
    message: str


class WatchlistAssetResponse(BaseModel):
    symbol: str
    status: str
    protected: bool
    reason: str | None = None


class ShadowIntentRequest(BaseModel):
    user_id: str
