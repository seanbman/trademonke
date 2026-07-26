import pytest
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from app.settings import Settings
from app.telegram.commands import BOT_COMMANDS, CommandResponse, CommandRouter
from app.telegram.service import TelegramService
from app.telemetry.db import Base, build_engine
from app.telemetry.models import (IndicatorAlertEventRecord, SetupRecord,
                                  SetupTransitionRecord)


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text) if reply_markup is None else (chat_id, text, reply_markup))

    async def answer_callback(self, callback_query_id, text=None):
        self.answered = (callback_query_id, text)

    async def set_commands(self, commands):
        self.commands = commands


@pytest.fixture
def telegram_parts():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(telegram_chat_id=-123, telegram_allowed_user_ids="42")
    client = FakeClient()
    router = CommandRouter(settings, Session)
    return settings, client, router, Session


def test_read_commands_and_persistent_controls(telegram_parts):
    _, _, router, Session = telegram_parts
    assert "Watchlist" in router.dispatch("/watchlist@trade_monke_bot", 42)
    pending = router.dispatch("/watchlist probe SOL/USDT", 42)
    change_id = pending.text.split("/watchlist confirm ", 1)[1]
    assert "now probe" in router.dispatch(f"/watchlist confirm {change_id}", 42).text
    assert "pending" in router.dispatch("/backfill SOL/USDT", 42)
    assert "Backfill status for all tracked assets" in router.dispatch("/backfill", 42)
    request = router.dispatch("/backfill request SOL/USDT 30 1h", 42)
    request_id = request.text.split("/backfill confirm ", 1)[1]
    assert "Backfill queued" in router.dispatch(f"/backfill confirm {request_id}", 42).text
    assert "enabled" in router.dispatch("/alerts enable BTC/USDT", 42)
    assert "minimum score" in router.dispatch("/alerts score BTC/USDT 5", 42)
    alert_report = router.dispatch("/alerts", 42)
    assert "Effective alerts" in alert_report
    assert "BTC/USDT [active]: setup=ON(explicit≥5); indicators=*; score≥5" in alert_report
    assert "ETH/USDT [active]: setup=ON(default≥4); indicators=off" in alert_report
    assert "confirmation required" in router.dispatch("/kill", 42).lower()
    assert "KILL SWITCH ACTIVE" in router.dispatch("/kill confirm", 42)
    assert "kill_switch=ON" in router.dispatch("/status", 42)
    assert "Cannot resume" in router.dispatch("/resume", 42)
    with Session() as session:
        assert session.execute(__import__("sqlalchemy").text("select count(*) from events")).scalar() == 2


def test_registered_command_menu_is_valid_and_current():
    names = [item["command"] for item in BOT_COMMANDS]
    assert len(names) == len(set(names))
    assert {"health", "watchlist", "backfill", "indicators", "alerts", "kill", "help"} <= set(names)
    assert all(name.islower() and name.replace("_", "").isalnum() for name in names)
    assert all(1 <= len(item["description"]) <= 256 for item in BOT_COMMANDS)


def test_marketdata_line_explains_open_close_and_freshness():
    opened = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    current = CommandRouter._marketdata_line(
        "BTC/USDT", "4h", opened, datetime(2026, 7, 11, 18, 5, tzinfo=timezone.utc))
    assert "12:00 → 2026-07-11 16:00" in current
    assert "CURRENT · next closes in 1h 55m" in current
    overdue = CommandRouter._marketdata_line(
        "BTC/USDT", "4h", opened, datetime(2026, 7, 11, 20, 30, tzinfo=timezone.utc))
    assert "OVERDUE by 30m" in overdue


def test_setup_and_why_commands_explain_persisted_evidence(telegram_parts):
    _, _, router, Session = telegram_parts
    now = datetime.now(timezone.utc)
    components = {name: {"passed": name in {"htf_bias", "structure"}}
                  for name in ("htf_bias", "liquidity_sweep", "fvg_retest",
                               "retest_confirmation", "smt", "structure")}
    with Session() as session:
        session.add(SetupRecord(id="stp_test", pair="BTC/USDT", timeframe="5m", direction="long",
                                state="developing", highest_state_reached="developing",
                                components={"score": 2, "components": components,
                                "last_candle_timestamp": now.isoformat(), "execution_connected": False},
                                detected_at=now, strategy_version="v1", config_hash="cfg", git_sha="sha"))
        session.add(SetupTransitionRecord(setup_id="stp_test", from_state="none",
                                          to_state="developing", occurred_at=now,
                                          reason="two components passed"))
        session.commit()
    detail = router.dispatch("/setup stp_test", 42)
    explanation = router.dispatch("/why stp_test", 42)
    assert "score: 2/6" in detail and "Execution connected: no" in detail
    assert "Passing: htf_bias, structure" in explanation
    assert "Missing: liquidity_sweep" in explanation


@pytest.mark.anyio
async def test_service_restricts_chat_and_user(telegram_parts):
    settings, client, router, _ = telegram_parts
    service = TelegramService(settings, client, router)
    assert not await service.process_update({"message": {"chat": {"id": -999}, "from": {"id": 42}, "text": "/health"}})
    assert not await service.process_update({"message": {"chat": {"id": -123}, "from": {"id": 7}, "text": "/health"}})
    assert await service.process_update({"message": {"chat": {"id": -123}, "from": {"id": 42}, "text": "/health"}})
    assert client.sent[-1][0] == -123


@pytest.mark.anyio
async def test_service_delivers_matching_indicator_alert_once(telegram_parts):
    settings, client, router, Session = telegram_parts
    router.dispatch("/alerts enable BTC/USDT", 42)
    now = datetime.now(timezone.utc)
    with Session() as session:
        session.add(IndicatorAlertEventRecord(
            event_id="indicator-test", exchange="okx", symbol="BTC/USDT", timeframe="5m",
            candle_timestamp=now, direction="long", event_type="component_change",
            component="structure", old_value="False", new_value="True", score=4,
            message="BTC structure ON", created_at=now, delivered_at=None))
        session.commit()
    service = TelegramService(settings, client, router)
    assert await service.drain_alerts() == 1
    assert await service.drain_alerts() == 0
    assert client.sent[-1] == (-123, "Indicator alert:\nBTC structure ON")


@pytest.mark.anyio
async def test_service_delivers_setup_alert_without_explicit_subscription(telegram_parts):
    settings, client, router, Session = telegram_parts
    router.dispatch("/watchlist", 42)  # initializes protected active anchors
    now = datetime.now(timezone.utc)
    with Session() as session:
        session.add(IndicatorAlertEventRecord(
            event_id="setup-default-alert", exchange="okx", symbol="ETH/USDT", timeframe="5m",
            candle_timestamp=now, direction="long", event_type="setup_transition",
            component="setup_state", old_value="none", new_value="watch", score=4,
            message="ETH setup detected", created_at=now, delivered_at=None))
        session.commit()
    service = TelegramService(settings, client, router)
    assert await service.drain_alerts() == 1
    assert client.sent[-1] == (-123, "Setup alert:\nETH setup detected")


def test_guided_menus_and_confirmation_buttons(telegram_parts):
    _, _, router, _ = telegram_parts
    root = router.dispatch("/menu", 42)
    assert isinstance(root, CommandResponse)
    assert any(button["callback_data"] == "m:alerts"
               for row in root.reply_markup["inline_keyboard"] for button in row)
    alerts = router.dispatch("/alerts menu", 42)
    assert any(button["callback_data"] == "a:BTC"
               for row in alerts.reply_markup["inline_keyboard"] for button in row)
    action = router.dispatch_callback("a:BTC", 42)
    assert "Alert settings for BTC/USDT" in action.text
    setup_only = router.dispatch_callback("aa:setup:BTC", 42)
    assert "setup lifecycle alerts only" in setup_only.text

    request = router.dispatch_callback("br:30:BTC", 42)
    confirm_data = request.reply_markup["inline_keyboard"][0][0]["callback_data"]
    assert confirm_data.startswith("bc:br_")
    queued = router.dispatch_callback(confirm_data, 42)
    assert "Backfill queued" in queued.text
    dashboard = router.dispatch_callback("m:backfill", 42)
    assert "Backfill status for all tracked assets" in dashboard.text
    assert any(button["callback_data"] == "ba:sync"
               for row in dashboard.reply_markup["inline_keyboard"] for button in row)

    pending = router.dispatch("/watchlist probe SOL/USDT", 42)
    change_id = pending.text.split("/watchlist confirm ", 1)[1]
    router.dispatch(f"/watchlist confirm {change_id}", 42)
    removal = router.dispatch_callback("wa:disabled:SOL", 42)
    watch_confirm = removal.reply_markup["inline_keyboard"][0][0]["callback_data"]
    assert watch_confirm.startswith("wc:ch_")
    confirmed = router.dispatch_callback(watch_confirm, 42)
    assert "is now disabled" in confirmed.text


@pytest.mark.anyio
async def test_callback_queries_enforce_chat_and_user_authorization(telegram_parts):
    settings, client, router, _ = telegram_parts
    service = TelegramService(settings, client, router)
    unauthorized = {"callback_query": {"id": "cb1", "data": "m:root",
                                        "from": {"id": 7},
                                        "message": {"chat": {"id": -123}}}}
    assert not await service.process_update(unauthorized)
    assert client.answered == ("cb1", "Unauthorized")
    authorized = {"callback_query": {"id": "cb2", "data": "m:root",
                                      "from": {"id": 42},
                                      "message": {"chat": {"id": -123}}}}
    assert await service.process_update(authorized)
    assert client.answered == ("cb2", None)
    assert client.sent[-1][1] == "TradeMonke guided menu:"
