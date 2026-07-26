import asyncio
import ccxt
import json
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import websockets
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.settings import Settings, get_settings
from app.runtime import should_embed_market_relay
from app.api.workstation import build_workstation_snapshot, snapshot_fingerprint
from app.relay.hub import GuiSubscription, relay_hub
from app.relay.workstation import truncate_chart_for_cache
from app.execution.adapter import ExecutionGateError, FreqtradeIntentAdapter
from app.telemetry.db import SessionLocal
from app.telemetry.models import (ControlStateRecord, EpisodeEventRecord, EventRecord,
                                  AlertAcknowledgementRecord, GuiActionEventRecord,
                                  ImbalanceRecord, LiquidityLevelRecord, RecommendationRecord,
                                  ServiceHeartbeatRecord, SetupRecord, StrategyEpisodeRecord,
                                  WatchlistAssetRecord, CandleRecord, IndicatorAlertEventRecord,
                                  IndicatorSnapshotRecord)
from app.telemetry.models import OrderEventRecord, TradePlanRecord
from app.market_data.exchange import ReadOnlyExchange
from app.market_data.storage import latest_candles
from app.market_data.live import LiveMarketRelay
from app.market_data.symbol_search import (enrich_hits_with_closes, enrich_hits_with_tickers,
                                          latest_candidate_evidence, search_known_symbols,
                                          search_spot_markets, watchlist_index)
from app.market_data.watchlist import confirm_change, create_change
from app.telemetry.repository import list_setups, record_heartbeat
from app.domain.models import Candle
from app.domain.patterns import detect_patterns

from .schemas import (AlertAcknowledgementRequest, AlertAcknowledgementResponse,
                      ChartDataResponse, CollectionResponse, EpisodeEventResponse,
                      EpisodeResponse, EventResponse, GuiBootstrapResponse, HealthResponse,
                      LiquidityLevelResponse, MarketDataStatus, RecommendationResponse,
                      SetupResponse, ShadowIntentRequest, ShadowReconciliationRequest,
                      SymbolSearchHitResponse, SymbolSearchResponse,
                      WatchlistAssetResponse, WatchlistChangeRequest,
                      WatchlistChangeResponse, WatchlistConfirmRequest)

GUI_DIST = Path(__file__).resolve().parents[2] / "gui" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    relay_hub.cache.ttl = timedelta(hours=settings.relay_cache_hours)
    relay_task = None
    if not settings.is_relay_mode and should_embed_market_relay(settings.embed_market_relay):
        relay = LiveMarketRelay(
            settings.market_symbols, settings.market_timeframes,
            settings.market_stream_bind_host, settings.market_stream_port)
        relay_task = asyncio.create_task(relay.run_forever())
    try:
        yield
    finally:
        if relay_task is not None:
            relay_task.cancel()
            await asyncio.gather(relay_task, return_exceptions=True)


app = FastAPI(title="Private Trading Platform API", version="0.1.0", lifespan=lifespan)


def require_gui_access(x_gui_token: str | None = Header(default=None),
                       settings: Settings = Depends(get_settings)) -> None:
    if not settings.gui_access_token or not x_gui_token or not secrets.compare_digest(
            x_gui_token, settings.gui_access_token):
        raise HTTPException(401, "valid GUI access token required")


def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _enabled(session: Session, key: str) -> bool:
    control = session.get(ControlStateRecord, key)
    return bool(control and control.enabled)


@app.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings),
           session: Session = Depends(db_session)) -> HealthResponse:
    session.execute(text("SELECT 1"))
    record_heartbeat(session, "platform-api", settings.strategy_version, settings.git_sha)
    now = datetime.now(timezone.utc)
    streams = latest_candles(session)
    stale = 0
    for (_, _, timeframe), timestamp in streams.items():
        aware = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        if (now - aware).total_seconds() > (
                ccxt.Exchange.parse_timeframe(timeframe) * settings.market_data_stale_multiplier):
            stale += 1
    heartbeats = list(session.scalars(select(ServiceHeartbeatRecord)))
    service_states = {}
    for item in heartbeats:
        observed = item.observed_at if item.observed_at.tzinfo else item.observed_at.replace(tzinfo=timezone.utc)
        age = (now - observed).total_seconds()
        service_states[item.service] = item.status if age <= 120 else "stale"
    expected_services = ["platform-api", "market-data"]
    if settings.telegram_bot_token:
        expected_services.append("telegram-bot")
    for service in expected_services:
        service_states.setdefault(service, "missing")
    service_states["freqtrade"] = "disconnected" if settings.execution_mode != "dry_run" else "unverified"
    feed_status = "empty" if not streams else ("stale" if stale else "healthy")
    degraded = feed_status != "healthy" or any(value != "healthy" for value in service_states.values())
    return HealthResponse(
        status="degraded" if degraded else "healthy", dry_run=settings.dry_run,
        trading_mode=settings.trading_mode, kill_switch=_enabled(session, "kill_switch"),
        paused=_enabled(session, "paused"), database="healthy", feed_status=feed_status,
        stale_streams=stale, total_streams=len(streams), services=service_states,
        strategy_version=settings.strategy_version, git_sha=settings.git_sha)


@app.get("/setups", response_model=list[SetupResponse])
def setups(session: Session = Depends(db_session)):
    return list_setups(session)


@app.get("/setups/{setup_id}", response_model=SetupResponse)
def setup(setup_id: str, session: Session = Depends(db_session)):
    record = session.get(SetupRecord, setup_id)
    if record is None:
        raise HTTPException(404, "setup not found")
    return record


@app.get("/market-data/status", response_model=list[MarketDataStatus])
def market_data_status(session: Session = Depends(db_session), settings: Settings = Depends(get_settings)):
    now = datetime.now(timezone.utc)
    result = []
    for (exchange, symbol, timeframe), timestamp in latest_candles(session).items():
        aware = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        seconds = ccxt.Exchange.parse_timeframe(timeframe)
        age = (now - aware).total_seconds()
        result.append(MarketDataStatus(exchange=exchange, symbol=symbol, timeframe=timeframe,
                                       latest_closed_candle=aware, age_seconds=age,
                                       stale=age > seconds * settings.market_data_stale_multiplier))
    return result


@app.get("/events", response_model=list[EventResponse])
def events(limit: int = 100, session: Session = Depends(db_session)):
    limit = max(1, min(limit, 500))
    return list(session.scalars(select(EventRecord).order_by(
        EventRecord.occurred_at.desc()).limit(limit)))


@app.get("/liquidity-levels", response_model=list[LiquidityLevelResponse])
def liquidity_levels(session: Session = Depends(db_session)):
    return list(session.scalars(select(LiquidityLevelRecord).order_by(
        LiquidityLevelRecord.updated_at.desc())))


@app.get("/episodes", response_model=list[EpisodeResponse])
def episodes(session: Session = Depends(db_session)):
    return list(session.scalars(select(StrategyEpisodeRecord).order_by(
        StrategyEpisodeRecord.updated_at.desc())))


@app.get("/episodes/{episode_id}/events", response_model=list[EpisodeEventResponse],
         dependencies=[Depends(require_gui_access)])
def episode_events(episode_id: str, session: Session = Depends(db_session),
                   settings: Settings = Depends(get_settings)):
    if settings.is_relay_mode:
        for cached in relay_hub.cache.snapshots.values():
            by_episode = cached.payload.get("episode_events") or {}
            if episode_id in by_episode:
                return by_episode[episode_id]
            legacy = [
                item for item in (cached.payload.get("events") or [])
                if item.get("episode_id") == episode_id
            ]
            if legacy:
                return legacy
        return []
    if session.get(StrategyEpisodeRecord, episode_id) is None:
        raise HTTPException(404, "episode not found")
    return list(session.scalars(select(EpisodeEventRecord).where(
        EpisodeEventRecord.episode_id == episode_id).order_by(EpisodeEventRecord.occurred_at)))


@app.get("/recommendations", response_model=list[RecommendationResponse])
def recommendations(status: str | None = None, session: Session = Depends(db_session)):
    query = select(RecommendationRecord).order_by(RecommendationRecord.created_at.desc())
    if status:
        query = query.where(RecommendationRecord.status == status)
    return list(session.scalars(query))


def _gui_bootstrap_data(session: Session, settings: Settings) -> GuiBootstrapResponse:
    if settings.is_relay_mode and relay_hub.cache.snapshots:
        newest = max(relay_hub.cache.snapshots.values(), key=lambda item: item.generated_at)
        bootstrap = newest.payload.get("bootstrap") or {}
        return GuiBootstrapResponse(**bootstrap)
    return GuiBootstrapResponse(
        contract_version="gui.v1", generated_at=datetime.now(timezone.utc),
        watchlist=[{"symbol": item.symbol, "status": item.status, "protected": item.protected}
                   for item in session.scalars(select(WatchlistAssetRecord).order_by(
                       WatchlistAssetRecord.symbol))],
        setups=list_setups(session),
        episodes=list(session.scalars(select(StrategyEpisodeRecord).order_by(
            StrategyEpisodeRecord.updated_at.desc()))),
        recommendations=list(session.scalars(select(RecommendationRecord).order_by(
            RecommendationRecord.created_at.desc()))),
        controls={"paused": _enabled(session, "paused"),
                  "kill_switch": _enabled(session, "kill_switch")})


@app.get("/api/v1/gui/bootstrap", response_model=GuiBootstrapResponse,
         dependencies=[Depends(require_gui_access)])
def gui_bootstrap(session: Session = Depends(db_session), settings: Settings = Depends(get_settings)):
    return _gui_bootstrap_data(session, settings)


@app.get("/api/v1/gui/watchlist/search", response_model=SymbolSearchResponse,
         dependencies=[Depends(require_gui_access)])
async def gui_watchlist_search(q: str, limit: int = 25,
                               session: Session = Depends(db_session),
                               settings: Settings = Depends(get_settings)):
    query = q.strip()
    if len(query) < 1:
        raise HTTPException(400, "query parameter q is required")
    assets = watchlist_index(session)
    evidence = latest_candidate_evidence(session, settings.market_data_exchange)
    try:
        async with ReadOnlyExchange(settings.market_data_exchange) as exchange:
            hits = search_spot_markets(
                exchange.client.markets, query, settings.candidate_quote,
                watchlist=assets, evidence=evidence, limit=limit)
            tickers: dict = {}
            if hits:
                try:
                    tickers = await exchange.fetch_tickers()
                except Exception:
                    tickers = {}
            hits = enrich_hits_with_tickers(hits, tickers)
            source_note = settings.market_data_exchange
    except Exception:
        hits = search_known_symbols(
            session, settings.market_data_exchange, query,
            quote=settings.candidate_quote, limit=limit)
        closes: dict[str, object] = {}
        for hit in hits:
            candle = session.scalars(select(CandleRecord).where(
                CandleRecord.exchange == settings.market_data_exchange,
                CandleRecord.symbol == hit.symbol,
                CandleRecord.timeframe == settings.indicator_base_timeframe,
                CandleRecord.closed.is_(True),
            ).order_by(CandleRecord.timestamp.desc())).first()
            if candle is not None:
                closes[hit.symbol] = candle.close
        hits = enrich_hits_with_closes(hits, closes)
        source_note = f"{settings.market_data_exchange}:local"
    return SymbolSearchResponse(
        query=query, exchange=source_note, count=len(hits),
        items=[SymbolSearchHitResponse(**hit.__dict__) for hit in hits])


@app.post("/api/v1/gui/watchlist/changes", response_model=WatchlistChangeResponse,
          dependencies=[Depends(require_gui_access)])
def gui_watchlist_create_change(request: WatchlistChangeRequest,
                                session: Session = Depends(db_session),
                                settings: Settings = Depends(get_settings)):
    action = request.action.strip().lower()
    target = {"probe": "probe", "add": "active", "remove": "disabled"}.get(action)
    if target is None:
        raise HTTPException(400, "action must be probe, add, or remove")
    try:
        # GUI uses a stable synthetic numeric id for the confirmation audit trail.
        change = create_change(session, request.symbol, target, 0, request.reason)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    _audit_watchlist_action(session, settings, request.user_id, "watchlist_change_requested",
                            change.id, {"symbol": change.symbol, "target_status": target})
    return WatchlistChangeResponse(
        change_id=change.id, symbol=change.symbol, target_status=change.target_status,
        state=change.state, expires_at=change.expires_at,
        message=f"Pending: {change.symbol} → {target}. Confirm within 15 minutes.")


@app.post("/api/v1/gui/watchlist/changes/{change_id}/confirm",
          response_model=WatchlistAssetResponse,
          dependencies=[Depends(require_gui_access)])
def gui_watchlist_confirm_change(change_id: str, request: WatchlistConfirmRequest,
                                 session: Session = Depends(db_session),
                                 settings: Settings = Depends(get_settings)):
    try:
        asset = confirm_change(
            session, change_id, 0, settings.market_data_exchange,
            settings.candidate_min_quote_volume, settings.candidate_max_spread_bps,
            backfill_timeframes=settings.market_timeframes,
            backfill_days=settings.market_data_history_days)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    _audit_watchlist_action(session, settings, request.user_id, "watchlist_change_confirmed",
                            change_id, {"symbol": asset.symbol, "status": asset.status})
    return WatchlistAssetResponse(
        symbol=asset.symbol, status=asset.status, protected=asset.protected, reason=asset.reason)


@app.get("/api/v1/gui/chart/{symbol:path}", response_model=ChartDataResponse,
         dependencies=[Depends(require_gui_access)])
def gui_chart(symbol: str, timeframe: str = "5m", limit: int = 500,
              session: Session = Depends(db_session), settings: Settings = Depends(get_settings)):
    limit = max(1, min(limit, 2000))
    candles = list(session.scalars(select(CandleRecord).where(
        CandleRecord.exchange == settings.market_data_exchange,
        CandleRecord.symbol == symbol, CandleRecord.timeframe == timeframe,
        CandleRecord.closed.is_(True)).order_by(CandleRecord.timestamp.desc()).limit(limit)))
    candles.reverse()
    levels = list(session.scalars(select(LiquidityLevelRecord).where(
        LiquidityLevelRecord.exchange == settings.market_data_exchange,
        LiquidityLevelRecord.symbol == symbol, LiquidityLevelRecord.timeframe == timeframe)))
    episode_rows = list(session.scalars(select(StrategyEpisodeRecord).where(
        StrategyEpisodeRecord.exchange == settings.market_data_exchange,
        StrategyEpisodeRecord.symbol == symbol, StrategyEpisodeRecord.timeframe == timeframe)))
    episode_ids = [item.id for item in episode_rows]
    recommendations = [] if not episode_ids else list(session.scalars(select(
        RecommendationRecord).where(RecommendationRecord.episode_id.in_(episode_ids))))
    imbalances = list(session.scalars(select(ImbalanceRecord).where(
        ImbalanceRecord.exchange == settings.market_data_exchange,
        ImbalanceRecord.symbol == symbol, ImbalanceRecord.timeframe == timeframe)))
    indicator_snapshots = []
    for direction in ("long", "short"):
        snapshot = session.scalar(select(IndicatorSnapshotRecord).where(
            IndicatorSnapshotRecord.exchange == settings.market_data_exchange,
            IndicatorSnapshotRecord.symbol == symbol,
            IndicatorSnapshotRecord.timeframe == timeframe,
            IndicatorSnapshotRecord.direction == direction,
        ).order_by(IndicatorSnapshotRecord.candle_timestamp.desc()).limit(1))
        if snapshot is not None:
            indicator_snapshots.append(snapshot)
    domain_candles = [
        Candle(item.timestamp, item.open, item.high, item.low, item.close, item.volume)
        for item in candles
    ]
    patterns = [item.to_chart_dict() for item in detect_patterns(domain_candles)]
    return ChartDataResponse(
        contract_version="chart.v1", exchange=settings.market_data_exchange,
        symbol=symbol, timeframe=timeframe,
        candles=[{"timestamp": item.timestamp, "open": item.open, "high": item.high,
                  "low": item.low, "close": item.close, "volume": item.volume}
                 for item in candles], liquidity_levels=levels,
        imbalances=[{"id": item.id, "episode_id": item.episode_id,
                     "direction": item.direction, "type": item.imbalance_type,
                     "lower_price": item.lower_price, "upper_price": item.upper_price,
                     "status": item.status, "created_at": item.created_at}
                    for item in imbalances],
        episodes=episode_rows, recommendations=recommendations,
        indicator_snapshots=indicator_snapshots,
        patterns=patterns)


@app.get("/api/v1/events/stream", dependencies=[Depends(require_gui_access)])
def event_stream(after: datetime | None = None, session: Session = Depends(db_session)):
    query = select(EventRecord).order_by(EventRecord.occurred_at, EventRecord.event_id).limit(500)
    if after is not None:
        query = query.where(EventRecord.occurred_at > after)
    rows = list(session.scalars(query))

    def generate():
        for fallback_sequence, item in enumerate(rows, start=1):
            payload = {"contract_version": "events.v1",
                       "sequence": item.sequence or fallback_sequence,
                       "event_id": item.event_id, "event_type": item.event_type,
                       "schema_version": item.schema_version,
                       "occurred_at": item.occurred_at.isoformat(),
                       "correlation_id": item.correlation_id}
            yield f"id: {item.event_id}\nevent: {item.event_type}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/v1/gui/health", response_model=HealthResponse,
         dependencies=[Depends(require_gui_access)])
def gui_health(settings: Settings = Depends(get_settings), session: Session = Depends(db_session)):
    return health(settings, session)


@app.get("/api/v1/gui/alerts", dependencies=[Depends(require_gui_access)])
def gui_alerts(limit: int = 100, session: Session = Depends(db_session)):
    rows = list(session.scalars(select(IndicatorAlertEventRecord).order_by(
        IndicatorAlertEventRecord.created_at.desc()).limit(max(1, min(limit, 500)))))
    acknowledged = set(session.scalars(select(AlertAcknowledgementRecord.alert_event_id)))
    return [{"event_id": item.event_id, "symbol": item.symbol, "timeframe": item.timeframe,
             "event_type": item.event_type, "score": item.score, "message": item.message,
             "created_at": item.created_at, "acknowledged": item.event_id in acknowledged}
            for item in rows]


@app.post("/api/v1/gui/alerts/{event_id}/ack", response_model=AlertAcknowledgementResponse,
          dependencies=[Depends(require_gui_access)])
def acknowledge_alert(event_id: str, request: AlertAcknowledgementRequest,
                      settings: Settings = Depends(get_settings), session: Session = Depends(db_session)):
    alert = session.scalar(select(IndicatorAlertEventRecord).where(
        IndicatorAlertEventRecord.event_id == event_id))
    if alert is None:
        raise HTTPException(404, "alert not found")
    now = datetime.now(timezone.utc)
    acknowledgement = session.scalar(select(AlertAcknowledgementRecord).where(
        AlertAcknowledgementRecord.alert_event_id == event_id,
        AlertAcknowledgementRecord.user_id == request.user_id))
    if acknowledgement is None:
        acknowledgement = AlertAcknowledgementRecord(
            alert_event_id=event_id, user_id=request.user_id, acknowledged_at=now,
            snoozed_until=request.snoozed_until, escalation_status=None,
            navigation_target={"symbol": alert.symbol, "event_type": alert.event_type},
            note=request.note)
        session.add(acknowledgement)
    else:
        acknowledgement.acknowledged_at = now
        acknowledgement.snoozed_until = request.snoozed_until
        acknowledgement.note = request.note
    session.add(GuiActionEventRecord(
        event_id=f"gui:alert_ack:{event_id}:{request.user_id}:{int(now.timestamp())}",
        user_id=request.user_id, session_id=None, action_type="alert_acknowledged",
        occurred_at=now, entity_type="alert", entity_id=event_id,
        proposal={}, decision={"status": "accepted"}, reason=request.note,
        correlation_id=f"alert:{event_id}", strategy_version=settings.strategy_version,
        config_hash=settings.config_hash, git_sha=settings.git_sha))
    session.commit()
    return AlertAcknowledgementResponse(
        alert_event_id=event_id, user_id=request.user_id, acknowledged_at=now,
        snoozed_until=request.snoozed_until)


@app.get("/api/v1/gui/execution", dependencies=[Depends(require_gui_access)])
def gui_execution(settings: Settings = Depends(get_settings), session: Session = Depends(db_session)):
    plans = list(session.scalars(select(TradePlanRecord).order_by(
        TradePlanRecord.created_at.desc()).limit(100)))
    events = list(session.scalars(select(OrderEventRecord).order_by(
        OrderEventRecord.occurred_at.desc()).limit(200)))
    return {
        "contract_version": "execution-console.v1", "mode": settings.execution_mode,
        "dry_run_submission_locked": True,
        "gate_reason": "reviewed baseline and shadow reconciliation required",
        "controls": {"paused": _enabled(session, "paused"),
                     "kill_switch": _enabled(session, "kill_switch")},
        "plans": [{"id": plan.id, "status": plan.status, "version": plan.version,
                   "recommendation_id": plan.recommendation_id,
                   "entry": plan.entry_geometry, "targets": plan.targets,
                   "stop": plan.initial_stop, "size": plan.position_size,
                   "execution_connected": plan.validity.get("execution_connected", False)}
                  for plan in plans],
        "events": [{"event_id": event.event_id, "trade_plan_id": event.trade_plan_id,
                    "event_type": event.event_type, "occurred_at": event.occurred_at,
                    "snapshot": event.order_snapshot, "reason_codes": event.reason_codes}
                   for event in events],
    }


def _workstation_snapshot(symbol: str, timeframe: str, settings: Settings) -> dict:
    """Build one authoritative, closed-candle workstation view."""
    with SessionLocal() as session:
        return build_workstation_snapshot(
            symbol, timeframe, settings, session,
            bootstrap_builder=lambda active_session: _gui_bootstrap_data(active_session, settings),
            chart_builder=gui_chart,
            health_builder=health,
            alerts_builder=gui_alerts,
            execution_builder=gui_execution,
        )


def _snapshot_fingerprint(payload: dict) -> str:
    return snapshot_fingerprint(payload)


async def _send_workstation_refresh(websocket: WebSocket, symbol: str, timeframe: str,
                                    settings: Settings, last_fingerprint: str | None) -> str:
    payload = await asyncio.to_thread(_workstation_snapshot, symbol, timeframe, settings)
    fingerprint = _snapshot_fingerprint(payload)
    generated_at = datetime.now(timezone.utc).isoformat()
    if fingerprint != last_fingerprint:
        await websocket.send_json({
            "contract_version": "workstation.v1",
            "type": "snapshot",
            "generated_at": generated_at,
            "data": payload,
        })
    else:
        await websocket.send_json({
            "contract_version": "workstation.v1",
            "type": "heartbeat",
            "generated_at": generated_at,
        })
    return fingerprint


def _forward_to_gui(live: dict, selected_symbol: str, selected_timeframe: str,
                    price_timeframe: str) -> bool:
    if (live.get("contract_version") == "live-price.v1" and
            live.get("authoritative") is False):
        return True
    if live.get("contract_version") != "live-candle.v1" or live.get("authoritative") is not False:
        return False
    selected_candle = (live.get("symbol") == selected_symbol and
                       live.get("timeframe") == selected_timeframe)
    watchlist_price = live.get("timeframe") == price_timeframe
    return selected_candle or watchlist_price


def _feeder_status_message(status: str) -> dict:
    return {
        "contract_version": "feeder-status.v1",
        "type": "feeder_status",
        "status": status,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _forward_live_market(websocket: WebSocket, symbol: str, timeframe: str,
                               settings: Settings, last_fingerprint: str) -> str:
    async with websockets.connect(
            settings.market_stream_url, open_timeout=5, ping_interval=20, ping_timeout=20) as market:
        observed_at = datetime.now(timezone.utc).isoformat()
        await websocket.send_json(_feeder_status_message("live"))
        await websocket.send_json({
            "contract_version": "market-stream-status.v1",
            "type": "market_status",
            "status": "connected",
            "observed_at": observed_at,
        })
        market_receive = asyncio.create_task(market.recv())
        browser_receive = asyncio.create_task(websocket.receive())
        next_refresh = time.monotonic() + 5
        try:
            while True:
                timeout = max(0, next_refresh - time.monotonic())
                done, _ = await asyncio.wait(
                    {market_receive, browser_receive}, timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED)
                if browser_receive in done:
                    message = browser_receive.result()
                    if message["type"] == "websocket.disconnect":
                        raise WebSocketDisconnect
                    browser_receive = asyncio.create_task(websocket.receive())
                if market_receive in done:
                    live = json.loads(market_receive.result())
                    market_receive = asyncio.create_task(market.recv())
                    if _forward_to_gui(
                            live, symbol, timeframe, settings.indicator_base_timeframe):
                        await websocket.send_json(live)
                if time.monotonic() >= next_refresh:
                    last_fingerprint = await _send_workstation_refresh(
                        websocket, symbol, timeframe, settings, last_fingerprint)
                    next_refresh = time.monotonic() + 5
        finally:
            market_receive.cancel()
            browser_receive.cancel()
            await asyncio.gather(market_receive, browser_receive, return_exceptions=True)


@app.websocket("/api/v1/relay/ws")
async def relay_websocket(websocket: WebSocket):
    """Accept workstation snapshots pushed from the local data brain."""
    await websocket.accept()
    settings = get_settings()
    try:
        request = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = request.get("token") if isinstance(request, dict) else None
        if (request.get("type") != "authenticate" or not settings.feeder_token or
                not isinstance(token, str) or
                not secrets.compare_digest(token, settings.feeder_token)):
            await websocket.close(code=1008, reason="valid feeder token required")
            return
        await relay_hub.set_feeder_connected(True)
        while True:
            message = await websocket.receive_json()
            if isinstance(message, dict):
                await relay_hub.ingest(message)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return
    finally:
        await relay_hub.set_feeder_connected(False)


async def _send_relay_snapshot(websocket: WebSocket, symbol: str, timeframe: str,
                               settings: Settings) -> None:
    await websocket.send_json(relay_hub.feeder_status_message())
    status = relay_hub.cache.feeder_status()
    cached = relay_hub.cache.get_snapshot(symbol, timeframe)
    if cached is None:
        return
    payload = dict(cached.payload)
    if status == "cached":
        payload = dict(payload)
        payload["chart"] = truncate_chart_for_cache(payload.get("chart") or {},
                                                    settings.relay_cache_hours)
        payload["events"] = []
    await websocket.send_json({
        "contract_version": "workstation.v1",
        "type": "snapshot",
        "generated_at": cached.generated_at.isoformat(),
        "fingerprint": cached.fingerprint,
        "data": payload,
    })


async def _gui_websocket_relay(websocket: WebSocket, symbol: str, timeframe: str,
                               settings: Settings) -> None:
    subscription = GuiSubscription(websocket, symbol, timeframe)
    await relay_hub.register_gui(subscription)
    try:
        await _send_relay_snapshot(websocket, symbol, timeframe, settings)
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=5)
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect
            except asyncio.TimeoutError:
                await websocket.send_json(relay_hub.feeder_status_message())
                if relay_hub.cache.feeder_status() == "offline":
                    await _send_relay_snapshot(websocket, symbol, timeframe, settings)
    finally:
        await relay_hub.unregister_gui(subscription)


@app.websocket("/api/v1/gui/ws")
async def gui_websocket(websocket: WebSocket):
    """Push workstation snapshots without exposing the GUI token in the URL."""
    await websocket.accept()
    try:
        request = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        settings = get_settings()
        if not isinstance(request, dict):
            await websocket.close(code=1008, reason="subscription object required")
            return
        token = request.get("token")
        if (request.get("type") != "subscribe" or not settings.gui_access_token or
                not isinstance(token, str) or
                not secrets.compare_digest(token, settings.gui_access_token)):
            await websocket.close(code=1008, reason="valid GUI access token required")
            return
        symbol = request.get("symbol")
        timeframe = request.get("timeframe")
        if not isinstance(symbol, str) or not isinstance(timeframe, str):
            await websocket.close(code=1008, reason="symbol and timeframe are required")
            return
        if settings.is_relay_mode:
            await _gui_websocket_relay(websocket, symbol, timeframe, settings)
            return
        with SessionLocal() as session:
            asset = session.get(WatchlistAssetRecord, symbol)
        if asset is None or asset.status not in {"active", "probe"}:
            await websocket.close(code=1008, reason="symbol is not on the active watchlist")
            return
        if timeframe not in settings.market_timeframes:
            await websocket.close(code=1008, reason="timeframe is not configured")
            return

        last_fingerprint = await _send_workstation_refresh(
            websocket, symbol, timeframe, settings, None)
        while True:
            try:
                last_fingerprint = await _forward_live_market(
                    websocket, symbol, timeframe, settings, last_fingerprint)
            except WebSocketDisconnect:
                return
            except Exception:
                await websocket.send_json(_feeder_status_message("offline"))
                await websocket.send_json({
                    "contract_version": "market-stream-status.v1",
                    "type": "market_status",
                    "status": "disconnected",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                })
                message = await asyncio.wait_for(websocket.receive(), timeout=5)
                if message["type"] == "websocket.disconnect":
                    return
            except asyncio.TimeoutError:
                last_fingerprint = await _send_workstation_refresh(
                    websocket, symbol, timeframe, settings, last_fingerprint)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return


def _audit_execution_action(session, settings, user_id, action, plan_id, decision, reason):
    now = datetime.now(timezone.utc)
    session.add(GuiActionEventRecord(
        event_id=f"gui:{action}:{plan_id}:{user_id}:{int(now.timestamp())}",
        user_id=user_id, session_id=None, action_type=action, occurred_at=now,
        entity_type="trade_plan", entity_id=plan_id, proposal={}, decision=decision,
        reason=reason, correlation_id=f"trade_plan:{plan_id}",
        strategy_version=settings.strategy_version, config_hash=settings.config_hash, git_sha=settings.git_sha))
    session.commit()


def _audit_watchlist_action(session, settings, user_id, action, entity_id, decision):
    now = datetime.now(timezone.utc)
    session.add(GuiActionEventRecord(
        event_id=f"gui:{action}:{entity_id}:{user_id}:{int(now.timestamp())}",
        user_id=user_id, session_id=None, action_type=action, occurred_at=now,
        entity_type="watchlist_change", entity_id=entity_id, proposal={}, decision=decision,
        reason=None, correlation_id=f"watchlist:{entity_id}",
        strategy_version=settings.strategy_version, config_hash=settings.config_hash,
        git_sha=settings.git_sha))
    session.commit()


@app.post("/api/v1/gui/execution/{plan_id}/shadow", dependencies=[Depends(require_gui_access)])
def create_shadow_intent(plan_id: str, request: ShadowIntentRequest,
                         settings: Settings = Depends(get_settings), session: Session = Depends(db_session)):
    adapter = FreqtradeIntentAdapter(lambda: SessionLocal(), settings.execution_mode,
                                     settings.strategy_version, settings.git_sha)
    try:
        event = adapter.create_intent(plan_id)
    except ExecutionGateError as error:
        _audit_execution_action(session, settings, request.user_id, "shadow_intent_rejected",
                                plan_id, {"status": "rejected"}, str(error))
        raise HTTPException(409, str(error)) from error
    _audit_execution_action(session, settings, request.user_id, "shadow_intent_created",
                            plan_id, {"status": "accepted", "event_id": event.event_id}, None)
    return {"event_id": event.event_id, "event_type": event.event_type,
            "submitted": event.order_snapshot["submitted"]}


@app.post("/api/v1/gui/execution/{plan_id}/reconcile", dependencies=[Depends(require_gui_access)])
def reconcile_shadow(plan_id: str, request: ShadowReconciliationRequest,
                     settings: Settings = Depends(get_settings), session: Session = Depends(db_session)):
    adapter = FreqtradeIntentAdapter(lambda: SessionLocal(), settings.execution_mode,
                                     settings.strategy_version, settings.git_sha)
    observation = {"would_fill": request.would_fill,
                   "slippage_bps": str(request.slippage_bps),
                   "observed_price": str(request.observed_price) if request.observed_price else None}
    try:
        event = adapter.reconcile_shadow(plan_id, observation)
    except ExecutionGateError as error:
        _audit_execution_action(session, settings, request.user_id, "shadow_reconciliation_rejected",
                                plan_id, {"status": "rejected"}, str(error))
        raise HTTPException(409, str(error)) from error
    _audit_execution_action(session, settings, request.user_id, "shadow_reconciled",
                            plan_id, {"status": "accepted", "event_id": event.event_id}, None)
    return {"event_id": event.event_id, "event_type": event.event_type,
            "submitted": event.order_snapshot["submitted"]}


def empty_collection() -> CollectionResponse:
    return CollectionResponse(items=[], count=0)


for path in ("/bots", "/trades", "/performance", "/watchlist", "/strategies"):
    app.add_api_route(path, empty_collection, methods=["GET"], response_model=CollectionResponse)


def mount_gui(settings: Settings) -> None:
    if getattr(app.state, "gui_mounted", False):
        return
    if not settings.serve_gui or not GUI_DIST.is_dir():
        return
    app.mount("/", StaticFiles(directory=GUI_DIST, html=True), name="gui")
    app.state.gui_mounted = True


mount_gui(get_settings())
