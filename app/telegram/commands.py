from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.market_data.storage import latest_candles
from app.market_data.candidates import STABLE_BASES
from app.settings import Settings
from app.market_data.watchlist import (audit_configured_history,
                                       collection_symbols,
                                       confirm_backfill_request, confirm_change,
                                       create_backfill_request, create_change,
                                       ensure_anchors, probe_eligibility)
from app.telemetry.models import (AlertSubscriptionRecord, BackfillJobRecord,
                                  CandidateEvidenceRecord,
                                  IndicatorSnapshotRecord, SetupRecord,
                                  SetupTransitionRecord,
                                  ServiceHeartbeatRecord,
                                  WatchlistAssetRecord)

from .alerts import set_enabled, set_minimum_score, set_setup_only, toggle_component
from .control import get_control, set_control

HELP = """TradeMonke research commands:
/menu - Open the guided button menu
/health - Platform and feed health
/status - Operating and safety state
/watchlist - Active research pairs
/candidate SOL/USDT - Show evidence for one asset
/backfill SOL/USDT - Show historical backfill progress
/backfill request SOL/USDT 365 - Request a manual backfill
/backfill confirm br_xxxxxxxx - Confirm a manual backfill
/indicators BTC/USDT - Show current six-component state
/alerts - Show your alert subscriptions
/alerts enable BTC/USDT - Enable transition alerts
/alerts disable BTC/USDT - Disable transition alerts
/alerts component BTC/USDT fvg_retest - Toggle a component filter
/alerts score BTC/USDT 4 - Set the minimum score alert
/watchlist probe SOL/USDT - Request research-only collection
/watchlist add SOL/USDT - Request promotion to active
/watchlist remove SOL/USDT - Request disable/archive
/watchlist confirm ch_xxxxxxxx - Confirm a pending change
/marketdata - Latest closed candles
/candidates - Explain candidate screening
/setups - Active recorded setups
/setup stp_xxxxx - Show one setup and current evidence
/why stp_xxxxx - Explain state, passing, missing, and transition reasons
/strategy - Strategy version and mode
/pause - Pause new research setups
/resume - Resume research setups
/kill confirm - Block all new entries
/help - Show this message"""


@dataclass(frozen=True)
class CommandResponse:
    text: str
    reply_markup: dict | None = None


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row]
                                for row in rows]}

BOT_COMMANDS = [
    {"command": "menu", "description": "Open the guided action menu"},
    {"command": "health", "description": "Check platform and market-feed health"},
    {"command": "status", "description": "Show operating and safety state"},
    {"command": "watchlist", "description": "View or manage tracked assets"},
    {"command": "marketdata", "description": "Show latest closed candles"},
    {"command": "candidates", "description": "Show adjacent asset candidates"},
    {"command": "candidate", "description": "Inspect one candidate symbol"},
    {"command": "backfill", "description": "Request or monitor historical data"},
    {"command": "indicators", "description": "Show current indicator states"},
    {"command": "alerts", "description": "Manage indicator-change alerts"},
    {"command": "setups", "description": "List active strategy setups"},
    {"command": "setup", "description": "Show one setup and its evidence"},
    {"command": "why", "description": "Explain why a setup has its state"},
    {"command": "strategy", "description": "Show strategy version and mode"},
    {"command": "pause", "description": "Pause new setup processing"},
    {"command": "resume", "description": "Resume after a normal pause"},
    {"command": "kill", "description": "Require confirmation to block entries"},
    {"command": "help", "description": "Show the full command guide"},
]


class CommandRouter:
    def __init__(self, settings: Settings, session_factory):
        self.settings = settings
        self.session_factory = session_factory

    def dispatch(self, text: str, user_id: int) -> str | CommandResponse:
        command, *args = text.strip().split()
        command = command.split("@", 1)[0].lower()
        with self.session_factory() as session:
            ensure_anchors(session, self.settings.market_symbols)
            handlers = {
                "/health": self.health, "/status": self.status,
                "/marketdata": self.marketdata, "/candidates": self.candidates,
                "/setups": self.setups, "/strategy": self.strategy, "/help": lambda _: HELP,
            }
            if command == "/menu":
                return self.root_menu()
            if command in handlers:
                return handlers[command](session)
            if command == "/candidate":
                return self.candidate(session, args)
            if command == "/backfill":
                return self.backfill_command(session, args, user_id)
            if command == "/indicators":
                if args and args[0].lower() == "menu":
                    return self.symbol_menu(session, "i", "Choose a symbol for indicators:")
                return self.indicators(session, args)
            if command == "/alerts":
                if args and args[0].lower() == "menu":
                    return self.symbol_menu(session, "a", "Choose a symbol for alert settings:")
                return self.alerts(session, args, user_id)
            if command == "/setup":
                return self.setup_detail(session, args)
            if command == "/why":
                return self.why(session, args)
            if command == "/watchlist":
                if args and args[0].lower() == "menu":
                    return self.symbol_menu(session, "w", "Choose a watchlist asset:", include_disabled=True)
                return self.watchlist(session, args, user_id)
            if command == "/pause":
                set_control(session, "paused", True, user_id, "Telegram /pause",
                            self.settings.strategy_version, self.settings.git_sha)
                return "Paused: new research setups and entries are blocked. Data collection continues."
            if command == "/resume":
                if get_control(session, "kill_switch"):
                    return "Cannot resume while the kill switch is active. Administrative reset is required locally."
                set_control(session, "paused", False, user_id, "Telegram /resume",
                            self.settings.strategy_version, self.settings.git_sha)
                return "Resumed: new research setup processing is permitted. Dry-run-only guard remains active."
            if command == "/kill":
                if not args or args[0].lower() != "confirm":
                    return "Safety confirmation required. Send /kill confirm to block all new entries."
                set_control(session, "kill_switch", True, user_id, "Telegram /kill confirm",
                            self.settings.strategy_version, self.settings.git_sha)
                set_control(session, "paused", True, user_id, "Kill switch also pauses setup processing",
                            self.settings.strategy_version, self.settings.git_sha)
                return "KILL SWITCH ACTIVE: all new entries and setup processing are blocked. Exits and data collection remain available."
            return "Unknown command. Send /help."

    def health(self, session: Session) -> str:
        try:
            session.execute(select(1))
            database = "ok"
        except Exception:
            database = "error"
        streams = latest_candles(session)
        stale = self._stale_count(streams)
        now = datetime.now(timezone.utc)
        services = []
        for item in session.scalars(select(ServiceHeartbeatRecord).order_by(
                ServiceHeartbeatRecord.service)):
            observed = (item.observed_at if item.observed_at.tzinfo else
                        item.observed_at.replace(tzinfo=timezone.utc))
            state = item.status if (now - observed).total_seconds() <= 120 else "stale"
            services.append(f"{item.service}:{state}")
        feed = "empty" if not streams else ("stale" if stale else "healthy")
        return (f"Health: database={database}; feed={feed}; market_streams={len(streams)}; "
                f"stale_streams={stale}; services={','.join(services) or 'none'}; "
                f"paused={get_control(session, 'paused')}; "
                f"kill_switch={get_control(session, 'kill_switch')}; "
                f"dry_run={self.settings.dry_run}; version={self.settings.strategy_version}; "
                f"git_sha={self.settings.git_sha}.")

    def status(self, session: Session) -> str:
        return (f"Mode: {'PAUSED' if get_control(session, 'paused') else 'ACTIVE'} research; "
                f"kill_switch={'ON' if get_control(session, 'kill_switch') else 'OFF'}; "
                f"trading={self.settings.trading_mode}; dry_run={self.settings.dry_run}; "
                f"exchange={self.settings.market_data_exchange}.")

    def watchlist(self, session: Session, args: list[str], user_id: int) -> str:
        if not args:
            assets = list(session.scalars(select(WatchlistAssetRecord).order_by(
                WatchlistAssetRecord.status, WatchlistAssetRecord.symbol)))
            if not assets:
                return "Watchlist is empty."
            lines = ["Watchlist:"]
            lines.extend(f"{asset.symbol}: {asset.status}{' (protected)' if asset.protected else ''}" for asset in assets)
            return "\n".join(lines)
        action = args[0].lower()
        if action == "confirm" and len(args) == 2:
            try:
                asset = confirm_change(session, args[1], user_id, self.settings.market_data_exchange,
                                       self.settings.candidate_min_quote_volume,
                                       self.settings.candidate_max_spread_bps)
                return CommandResponse(
                    f"Confirmed: {asset.symbol} is now {asset.status}. The collector reloads automatically.",
                    inline_keyboard([[('View asset', f"w:{asset.symbol.split('/')[0]}"),
                                      ("Main menu", "m:root")]]))
            except ValueError as error:
                return f"Watchlist change rejected: {error}"
        if action in {"probe", "add", "remove"} and len(args) == 2:
            target = {"probe": "probe", "add": "active", "remove": "disabled"}[action]
            try:
                change = create_change(session, args[1], target, user_id)
                return CommandResponse(
                    f"Pending: {change.symbol} → {target}. Expires in 15 minutes.\n"
                    f"Confirm with /watchlist confirm {change.id}",
                    inline_keyboard([[('✅ Confirm', f"wc:{change.id}"),
                                      ("Cancel", "m:watchlist")]]))
            except ValueError as error:
                return f"Watchlist request rejected: {error}"
        return "Usage: /watchlist | /watchlist probe|add|remove SYMBOL | /watchlist confirm CHANGE_ID"

    def marketdata(self, session: Session) -> str:
        streams = latest_candles(session)
        if not streams:
            return "No stored candles yet. Run market-data backfill or start the market-data service."
        lines = ["Latest completed candles (UTC):",
                 "Times show candle open → close; NEXT is when another completed candle is expected."]
        now = datetime.now(timezone.utc)
        for (_, symbol, timeframe), timestamp in sorted(streams.items()):
            aware = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
            lines.append(self._marketdata_line(symbol, timeframe, aware, now))
        return "\n".join(lines[:30])

    @classmethod
    def _marketdata_line(cls, symbol: str, timeframe: str,
                         opened: datetime, now: datetime) -> str:
        duration = timedelta(seconds=cls._timeframe_seconds(timeframe))
        closed = opened + duration
        next_close = closed + duration
        if now <= next_close:
            remaining = cls._compact_duration(next_close - now)
            status = f"CURRENT · next closes in {remaining}"
        else:
            overdue = cls._compact_duration(now - next_close)
            status = f"OVERDUE by {overdue}"
        return (f"{symbol} {timeframe}: {opened:%Y-%m-%d %H:%M} → "
                f"{closed:%Y-%m-%d %H:%M} · {status}")

    @staticmethod
    def _timeframe_seconds(timeframe: str) -> int:
        unit, amount = timeframe[-1], int(timeframe[:-1])
        return amount * {"m": 60, "h": 3600, "d": 86400}.get(unit, 60)

    @staticmethod
    def _compact_duration(value: timedelta) -> str:
        total_minutes = max(0, int(value.total_seconds() // 60))
        days, remainder = divmod(total_minutes, 1440)
        hours, minutes = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")
        return " ".join(parts)

    def candidates(self, session: Session) -> str:
        subquery = select(CandidateEvidenceRecord.symbol, func.max(CandidateEvidenceRecord.observed_at).label("latest")).group_by(CandidateEvidenceRecord.symbol).subquery()
        records = list(session.scalars(select(CandidateEvidenceRecord).join(
            subquery, (CandidateEvidenceRecord.symbol == subquery.c.symbol) &
            (CandidateEvidenceRecord.observed_at == subquery.c.latest)
        ).order_by(CandidateEvidenceRecord.quote_volume.desc()).limit(10)))
        records = [record for record in records if record.symbol.split("/", 1)[0] not in STABLE_BASES]
        if not records:
            return "No candidate snapshot yet. Keep market-data running or run `market-data candidates` locally."
        lines = ["Candidate probes (not automatic approvals):"]
        for item in records:
            spread = "n/a" if item.spread_bps is None else f"{float(item.spread_bps):.2f}bps"
            lines.append(f"{item.symbol}: volume ${float(item.quote_volume):,.0f}; spread {spread}; {item.recommendation}")
        lines.append("Use /candidate SYMBOL for eligibility details.")
        return "\n".join(lines)

    def candidate(self, session: Session, args: list[str]) -> str:
        if len(args) != 1:
            return "Usage: /candidate SOL/USDT"
        symbol = args[0].upper() if "/" in args[0] else f"{args[0].upper()}/USDT"
        if symbol.split("/", 1)[0] in STABLE_BASES:
            return f"{symbol}: EXCLUDE — stable/fiat-like base assets are not directional strategy candidates."
        evidence = session.scalar(select(CandidateEvidenceRecord).where(
            CandidateEvidenceRecord.exchange == self.settings.market_data_exchange,
            CandidateEvidenceRecord.symbol == symbol).order_by(CandidateEvidenceRecord.observed_at.desc()))
        asset = session.get(WatchlistAssetRecord, symbol)
        eligible, reasons = probe_eligibility(session, self.settings.market_data_exchange, symbol,
                                              self.settings.candidate_min_quote_volume,
                                              self.settings.candidate_max_spread_bps)
        if evidence is None:
            return f"{symbol}: no exchange evidence yet. It is not ready for admission."
        spread = "n/a" if evidence.spread_bps is None else f"{float(evidence.spread_bps):.2f} bps"
        decision = "READY FOR REVIEW" if eligible else "COLLECT PROBE DATA"
        details = "; ".join(reasons) if reasons else "all current admission gates pass"
        backfill = self._latest_backfill(session, symbol)
        backfill_text = self._format_backfill(backfill) if backfill else "not queued"
        return (f"{symbol}: {decision}\nStatus: {asset.status if asset else 'not tracked'}\n"
                f"24h quote volume: ${float(evidence.quote_volume):,.0f}\nSpread: {spread}\n"
                f"Backfill: {backfill_text}\nEvidence: {details}")

    def backfill_command(self, session: Session, args: list[str], user_id: int) -> str:
        if args and args[0].lower() == "menu":
            return self.backfill_menu(session)
        if not args:
            assets = list(session.scalars(select(WatchlistAssetRecord).where(
                WatchlistAssetRecord.status.in_(["active", "probe"])
            ).order_by(WatchlistAssetRecord.symbol)))
            if not assets:
                return "No active or probe watchlist assets."
            lines = ["Backfill status for all tracked assets:"]
            for asset in assets:
                job = self._latest_backfill(session, asset.symbol)
                lines.append(f"{asset.symbol}: {self._format_backfill(job) if job else 'no job'}")
            return "\n".join(lines)
        if args and args[0].lower() == "request" and len(args) in {2, 3, 4}:
            try:
                days = int(args[2]) if len(args) >= 3 else 365
                timeframes = tuple(value.strip() for value in args[3].split(",") if value.strip()) if len(args) == 4 else tuple(self.settings.market_timeframes)
                request = create_backfill_request(session, self.settings.market_data_exchange,
                                                  args[1], timeframes, days, user_id)
                return CommandResponse(
                    f"Pending backfill: {request.symbol}, {days} days, {','.join(timeframes)}. "
                    f"Expires in 15 minutes.\nConfirm with /backfill confirm {request.id}",
                    inline_keyboard([[('✅ Confirm', f"bc:{request.id}"),
                                      ("Cancel", "m:backfill")]]))
            except (ValueError, TypeError) as error:
                return f"Backfill request rejected: {error}"
        if args and args[0].lower() == "confirm" and len(args) == 2:
            try:
                job = confirm_backfill_request(session, args[1], user_id)
                return CommandResponse(
                    f"Backfill queued: {job.symbol}, job={job.id}. Monitor with /backfill {job.symbol}",
                    inline_keyboard([[('View progress', f"b:{job.symbol.split('/')[0]}"),
                                      ("Main menu", "m:root")]]))
            except ValueError as error:
                return f"Backfill confirmation rejected: {error}"
        if len(args) != 1:
            return "Usage: /backfill | /backfill SYMBOL | /backfill request SYMBOL [DAYS] [TF,TF] | /backfill confirm REQUEST_ID"
        symbol = args[0].upper() if "/" in args[0] else f"{args[0].upper()}/USDT"
        job = self._latest_backfill(session, symbol)
        return f"{symbol} backfill: {self._format_backfill(job)}" if job else f"{symbol}: no backfill job found."

    def indicators(self, session: Session, args: list[str]) -> str:
        if len(args) != 1:
            return "Usage: /indicators BTC/USDT"
        symbol = args[0].upper() if "/" in args[0] else f"{args[0].upper()}/USDT"
        records = list(session.scalars(select(IndicatorSnapshotRecord).where(
            IndicatorSnapshotRecord.exchange == self.settings.market_data_exchange,
            IndicatorSnapshotRecord.symbol == symbol
        ).order_by(IndicatorSnapshotRecord.candle_timestamp.desc()).limit(2)))
        if not records:
            return f"{symbol}: no indicator snapshot yet. Keep market-data running with sufficient history."
        lines = [f"{symbol} indicators:"]
        for record in records:
            states = ", ".join(f"{name}={'ON' if value.get('passed') else 'off'}"
                               for name, value in record.components.items())
            lines.append(f"{record.direction.upper()} {record.score}/6 [{record.setup_state}]\n{states}\nCandle: {record.candle_timestamp:%Y-%m-%d %H:%M UTC}")
        return "\n".join(lines)

    def alerts(self, session: Session, args: list[str], user_id: int) -> str:
        chat_id = self.settings.telegram_chat_id
        if not args:
            assets = list(session.scalars(select(WatchlistAssetRecord).order_by(
                WatchlistAssetRecord.status, WatchlistAssetRecord.symbol)))
            group_records = list(session.scalars(select(AlertSubscriptionRecord).where(
                AlertSubscriptionRecord.chat_id == str(chat_id))))
            own_records = {record.symbol: record for record in group_records
                           if record.user_id == str(user_id)}
            lines = ["Effective alerts:"]
            for asset in assets:
                relevant = [record for record in group_records if record.symbol == asset.symbol]
                latest = max(relevant, key=self._subscription_timestamp) if relevant else None
                tracked = asset.status in {"active", "probe"}
                setup_on = tracked and (latest is None or latest.enabled)
                setup_source = "default≥4" if latest is None else f"explicit≥{latest.minimum_score}"
                own = own_records.get(asset.symbol)
                if own and own.enabled:
                    indicators = ",".join(own.components) or "none"
                    indicator_text = f"{indicators}; score≥{own.minimum_score}"
                else:
                    indicator_text = "off"
                lines.append(f"{asset.symbol} [{asset.status}]: setup={'ON' if setup_on else 'off'}({setup_source}); indicators={indicator_text}")
            return "\n".join(lines)
        action = args[0].lower()
        try:
            if action in {"enable", "disable"} and len(args) == 2:
                symbol = args[1].upper() if "/" in args[1] else f"{args[1].upper()}/USDT"
                self._require_tracked(session, symbol)
                record = set_enabled(session, chat_id, user_id, symbol, action == "enable")
                return (f"Alerts for {symbol}: {'enabled' if record.enabled else 'explicitly disabled'}. "
                        "This preference also controls default setup lifecycle alerts for the group.")
            if action == "component" and len(args) == 3:
                symbol = args[1].upper() if "/" in args[1] else f"{args[1].upper()}/USDT"
                self._require_tracked(session, symbol)
                record = toggle_component(session, chat_id, user_id, symbol, args[2].lower())
                return f"{symbol} component alerts: {','.join(record.components) or 'none'}"
            if action == "score" and len(args) == 3:
                symbol = args[1].upper() if "/" in args[1] else f"{args[1].upper()}/USDT"
                self._require_tracked(session, symbol)
                record = set_minimum_score(session, chat_id, user_id, symbol, int(args[2]))
                return f"{symbol} minimum score alert: {record.minimum_score}/6"
        except (ValueError, TypeError) as error:
            return f"Alert change rejected: {error}"
        return "Usage: /alerts | /alerts enable|disable SYMBOL | /alerts component SYMBOL COMPONENT | /alerts score SYMBOL 0-6"

    @staticmethod
    def _require_tracked(session: Session, symbol: str) -> None:
        asset = session.get(WatchlistAssetRecord, symbol)
        if asset is None or asset.status not in {"active", "probe"}:
            raise ValueError(f"{symbol} must be active or probe")

    @staticmethod
    def _subscription_timestamp(record: AlertSubscriptionRecord) -> float:
        timestamp = record.updated_at if record.updated_at.tzinfo else record.updated_at.replace(tzinfo=timezone.utc)
        return timestamp.timestamp()

    def _latest_backfill(self, session: Session, symbol: str):
        return session.scalar(select(BackfillJobRecord).where(
            BackfillJobRecord.exchange == self.settings.market_data_exchange,
            BackfillJobRecord.symbol == symbol).order_by(BackfillJobRecord.requested_at.desc()))

    @staticmethod
    def _format_backfill(job: BackfillJobRecord) -> str:
        completed = len(job.completed_timeframes or [])
        total = len(job.timeframes or [])
        current = f", current={job.current_timeframe}" if job.current_timeframe else ""
        error = f", error={job.error_type}" if job.error_type else ""
        return (f"{job.status}, {completed}/{total} timeframes, "
                f"{job.rows_processed:,} rows processed{current}{error}, job={job.id}")

    def setups(self, session: Session) -> str:
        records = list(session.scalars(select(SetupRecord).where(
            SetupRecord.state.in_(["detected", "developing", "watch", "strong_watch", "eligible"])
        ).order_by(SetupRecord.detected_at.desc()).limit(10)))
        if not records:
            return "No active setups recorded."
        return "Active setups:\n" + "\n".join(
            f"{r.id}: {r.pair} {r.direction} {r.state} {r.components.get('score', 0)}/6"
            for r in records)

    def setup_detail(self, session: Session, args: list[str]) -> str:
        if len(args) != 1:
            return "Usage: /setup stp_xxxxxxxxxxxxxxxxxxxx"
        setup = session.get(SetupRecord, args[0])
        if setup is None:
            return "Setup not found."
        evidence = setup.components or {}
        components = evidence.get("components", {})
        lines = [f"{setup.id}: {setup.pair} {setup.direction.upper()}",
                 f"State: {setup.state}; score: {evidence.get('score', 0)}/6",
                 f"Detected: {setup.detected_at:%Y-%m-%d %H:%M UTC}",
                 f"Last candle: {evidence.get('last_candle_timestamp', 'unknown')}"]
        lines.extend(f"{name}: {'PASS' if value.get('passed') else 'missing'}"
                     for name, value in components.items())
        lines.append("Execution connected: no")
        return "\n".join(lines)

    def why(self, session: Session, args: list[str]) -> str:
        if len(args) != 1:
            return "Usage: /why stp_xxxxxxxxxxxxxxxxxxxx"
        setup = session.get(SetupRecord, args[0])
        if setup is None:
            return "Setup not found."
        evidence = setup.components or {}
        components = evidence.get("components", {})
        passing = [name for name, value in components.items() if value.get("passed")]
        missing = [name for name, value in components.items() if not value.get("passed")]
        transitions = list(session.scalars(select(SetupTransitionRecord).where(
            SetupTransitionRecord.setup_id == setup.id
        ).order_by(SetupTransitionRecord.occurred_at.desc()).limit(5)))
        lines = [f"Why {setup.id} is {setup.state}:",
                 f"Current score: {evidence.get('score', 0)}/6",
                 "Passing: " + (", ".join(passing) or "none"),
                 "Missing: " + (", ".join(missing) or "none")]
        if evidence.get("eligibility_gate"):
            lines.append("Gate: " + evidence["eligibility_gate"])
        lines.append("Recent transitions:")
        lines.extend(f"{item.from_state} → {item.to_state}: {item.reason}" for item in transitions)
        lines.append("Research only: this setup has no execution path.")
        return "\n".join(lines)

    def strategy(self, _: Session) -> str:
        return f"Strategy: FvgProEliteStrategy\nVersion: {self.settings.strategy_version}\nGit: {self.settings.git_sha}\nExecution: spot dry-run only"

    def root_menu(self) -> CommandResponse:
        return CommandResponse("TradeMonke guided menu:", inline_keyboard([
            [("📊 Indicators", "m:indicators"), ("🔔 Alerts", "m:alerts")],
            [("🕘 Backfills", "m:backfill"), ("👀 Watchlist", "m:watchlist")],
            [("🎯 Setups", "m:setups"), ("❤️ Health", "m:health")],
            [("Help", "m:help")],
        ]))

    def symbol_menu(self, session: Session, prefix: str, title: str,
                    include_disabled: bool = False) -> CommandResponse:
        query = select(WatchlistAssetRecord).order_by(WatchlistAssetRecord.symbol)
        if not include_disabled:
            query = query.where(WatchlistAssetRecord.status.in_(["active", "probe"]))
        assets = list(session.scalars(query))
        rows = [[(f"{asset.symbol} · {asset.status}", f"{prefix}:{asset.symbol.split('/')[0]}")]
                for asset in assets]
        rows.append([("← Main menu", "m:root")])
        return CommandResponse(title, inline_keyboard(rows))

    def dispatch_callback(self, data: str, user_id: int) -> str | CommandResponse:
        with self.session_factory() as session:
            ensure_anchors(session, self.settings.market_symbols)
            parts = data.split(":")
            if data == "m:root":
                return self.root_menu()
            if data == "m:health":
                return self.health(session)
            if data == "m:help":
                return HELP
            if data == "m:alerts":
                return self.symbol_menu(session, "a", "Choose a symbol for alert settings:")
            if data == "m:indicators":
                return self.symbol_menu(session, "i", "Choose a symbol for indicators:")
            if data == "m:backfill":
                return self.backfill_menu(session)
            if data == "m:watchlist":
                return self.symbol_menu(session, "w", "Choose a watchlist asset:", include_disabled=True)
            if data == "m:setups":
                return self.setup_menu(session)
            if len(parts) == 2 and parts[0] == "i":
                return self.indicators(session, [f"{parts[1]}/USDT"])
            if len(parts) == 2 and parts[0] == "a":
                return self.alert_action_menu(session, parts[1])
            if len(parts) == 3 and parts[0] == "aa":
                return self.apply_alert_callback(session, parts[1], parts[2], user_id)
            if len(parts) == 3 and parts[0] == "as":
                return self.apply_setup_threshold_callback(session, parts[1], parts[2], user_id)
            if len(parts) == 2 and parts[0] == "b":
                return self.backfill_action_menu(session, parts[1])
            if data == "ba:sync":
                return self.sync_all_backfills(session)
            if len(parts) == 3 and parts[0] == "br":
                return self.create_backfill_callback(session, parts[1], parts[2], user_id)
            if len(parts) == 2 and parts[0] == "bc":
                return self.confirm_backfill_callback(session, parts[1], user_id)
            if len(parts) == 2 and parts[0] == "w":
                return self.watchlist_action_menu(session, parts[1])
            if len(parts) == 3 and parts[0] == "wa":
                return self.create_watchlist_callback(session, parts[1], parts[2], user_id)
            if len(parts) == 2 and parts[0] == "wc":
                return self.confirm_watchlist_callback(session, parts[1], user_id)
            if len(parts) == 2 and parts[0] == "s":
                return self.setup_action_menu(session, parts[1])
            if len(parts) == 2 and parts[0] == "sd":
                return self.setup_detail(session, [parts[1]])
            if len(parts) == 2 and parts[0] == "sw":
                return self.why(session, [parts[1]])
            return "Unknown or expired menu action. Send /menu to start again."

    def alert_action_menu(self, session: Session, base: str) -> CommandResponse:
        symbol = f"{base}/USDT"
        self._require_tracked(session, symbol)
        return CommandResponse(f"Alert settings for {symbol}:", inline_keyboard([
            [("All indicator changes", f"aa:all:{base}"), ("Setup alerts only", f"aa:setup:{base}")],
            [("Setup ≥2", f"as:2:{base}"), ("Setup ≥4", f"as:4:{base}")],
            [("Setup ≥5", f"as:5:{base}"), ("Setup =6", f"as:6:{base}")],
            [("Enable", f"aa:enable:{base}"), ("Disable", f"aa:disable:{base}")],
            [("← Symbols", "m:alerts"), ("Main menu", "m:root")],
        ]))

    def apply_alert_callback(self, session: Session, action: str, base: str,
                             user_id: int) -> CommandResponse:
        symbol = f"{base}/USDT"
        self._require_tracked(session, symbol)
        if action == "all":
            record = set_enabled(session, self.settings.telegram_chat_id, user_id, symbol, True)
            record.components, record.minimum_score = ["*"], 4
            session.commit()
            text = f"{symbol}: all indicator changes plus automatic setup alerts enabled."
        elif action == "setup":
            set_setup_only(session, self.settings.telegram_chat_id, user_id, symbol)
            text = f"{symbol}: setup lifecycle alerts only."
        elif action in {"enable", "disable"}:
            set_enabled(session, self.settings.telegram_chat_id, user_id, symbol, action == "enable")
            text = f"{symbol}: alerts {action}d."
        else:
            return CommandResponse("Unknown alert action.")
        return CommandResponse(text, inline_keyboard([[('← Alert settings', f"a:{base}"), ("Main menu", "m:root")]]))

    def apply_setup_threshold_callback(self, session: Session, score: str, base: str,
                                       user_id: int) -> CommandResponse:
        symbol = f"{base}/USDT"
        self._require_tracked(session, symbol)
        record = set_minimum_score(session, self.settings.telegram_chat_id, user_id,
                                   symbol, int(score))
        return CommandResponse(
            f"{symbol}: setup and score/state alerts now start at {record.minimum_score}/6.",
            inline_keyboard([[('← Alert settings', f"a:{base}"), ("Main menu", "m:root")]]))

    def backfill_action_menu(self, session: Session, base: str) -> CommandResponse:
        symbol = f"{base}/USDT"
        self._require_tracked(session, symbol)
        job = self._latest_backfill(session, symbol)
        status = self._format_backfill(job) if job else "no job found"
        return CommandResponse(f"{symbol} backfill: {status}", inline_keyboard([
            [("30d admission (1h)", f"br:30:{base}")],
            [("365d full research", f"br:365:{base}")],
            [("← Symbols", "m:backfill"), ("Main menu", "m:root")],
        ]))

    def backfill_menu(self, session: Session) -> CommandResponse:
        assets = list(session.scalars(select(WatchlistAssetRecord).where(
            WatchlistAssetRecord.status.in_(["active", "probe"])
        ).order_by(WatchlistAssetRecord.symbol)))
        rows = []
        for asset in assets:
            job = self._latest_backfill(session, asset.symbol)
            status = job.status if job else "no job"
            if job and job.current_timeframe:
                status += f" · {job.current_timeframe}"
            rows.append([(f"{asset.symbol} · {status}", f"b:{asset.symbol.split('/')[0]}")])
        rows.append([("🔄 Sync missing history for all", "ba:sync")])
        rows.append([("← Main menu", "m:root")])
        return CommandResponse("Backfill status for all tracked assets:", inline_keyboard(rows))

    def sync_all_backfills(self, session: Session) -> CommandResponse:
        symbols = collection_symbols(session)
        queued = audit_configured_history(
            session, self.settings.market_data_exchange, symbols,
            self.settings.market_timeframes, self.settings.market_data_history_days)
        text = (f"History sync queued {len(queued)} job(s)." if queued else
                "No new jobs queued: history is covered, already attempted, or a job is active.")
        response = self.backfill_menu(session)
        return CommandResponse(text + "\n\n" + response.text, response.reply_markup)

    def create_backfill_callback(self, session: Session, period: str, base: str,
                                 user_id: int) -> CommandResponse:
        days = int(period)
        timeframes = ("1h",) if days == 30 else tuple(self.settings.market_timeframes)
        request = create_backfill_request(session, self.settings.market_data_exchange,
                                          f"{base}/USDT", timeframes, days, user_id)
        return CommandResponse(
            f"Confirm backfill for {request.symbol}: {days} days, {','.join(timeframes)}?",
            inline_keyboard([[('✅ Confirm', f"bc:{request.id}"), ("Cancel", "m:backfill")]]))

    def confirm_backfill_callback(self, session: Session, request_id: str,
                                  user_id: int) -> CommandResponse:
        try:
            job = confirm_backfill_request(session, request_id, user_id)
            return CommandResponse(f"Backfill queued: {job.symbol}, job={job.id}",
                                   inline_keyboard([[('View progress', f"b:{job.symbol.split('/')[0]}"),
                                                     ("Main menu", "m:root")]]))
        except ValueError as error:
            return CommandResponse(f"Backfill confirmation rejected: {error}")

    def watchlist_action_menu(self, session: Session, base: str) -> CommandResponse:
        symbol = f"{base}/USDT"
        asset = session.get(WatchlistAssetRecord, symbol)
        if asset is None:
            return CommandResponse("Watchlist asset not found.")
        rows = []
        if asset.status == "probe":
            rows.append([("Promote to active", f"wa:active:{base}"),
                         ("Disable", f"wa:disabled:{base}")])
        elif asset.status == "active" and not asset.protected:
            rows.append([("Move to probe", f"wa:probe:{base}"),
                         ("Disable", f"wa:disabled:{base}")])
        elif asset.status == "disabled":
            rows.append([("Restore as probe", f"wa:probe:{base}")])
        rows.append([("← Watchlist", "m:watchlist"), ("Main menu", "m:root")])
        return CommandResponse(f"{symbol}: {asset.status}{' (protected)' if asset.protected else ''}",
                               inline_keyboard(rows))

    def create_watchlist_callback(self, session: Session, target: str, base: str,
                                  user_id: int) -> CommandResponse:
        try:
            change = create_change(session, f"{base}/USDT", target, user_id, "Telegram menu request")
            return CommandResponse(f"Confirm {change.symbol} → {target}?",
                                   inline_keyboard([[('✅ Confirm', f"wc:{change.id}"),
                                                     ("Cancel", f"w:{base}")]]))
        except ValueError as error:
            return CommandResponse(f"Watchlist request rejected: {error}")

    def confirm_watchlist_callback(self, session: Session, change_id: str,
                                   user_id: int) -> CommandResponse:
        try:
            asset = confirm_change(session, change_id, user_id, self.settings.market_data_exchange,
                                   self.settings.candidate_min_quote_volume,
                                   self.settings.candidate_max_spread_bps)
            return CommandResponse(f"Confirmed: {asset.symbol} is now {asset.status}.",
                                   inline_keyboard([[('View asset', f"w:{asset.symbol.split('/')[0]}"),
                                                     ("Main menu", "m:root")]]))
        except ValueError as error:
            return CommandResponse(f"Watchlist confirmation rejected: {error}")

    def setup_menu(self, session: Session) -> CommandResponse:
        setups = list(session.scalars(select(SetupRecord).where(
            SetupRecord.state.in_(["detected", "developing", "watch", "strong_watch", "eligible"])
        ).order_by(SetupRecord.detected_at.desc()).limit(10)))
        rows = [[(f"{item.pair} {item.direction} · {item.state} {item.components.get('score', 0)}/6",
                  f"s:{item.id}")] for item in setups]
        rows.append([("← Main menu", "m:root")])
        return CommandResponse("Choose an active setup:" if setups else "No active setups.",
                               inline_keyboard(rows))

    def setup_action_menu(self, session: Session, setup_id: str) -> CommandResponse:
        setup = session.get(SetupRecord, setup_id)
        if setup is None:
            return CommandResponse("Setup not found.")
        return CommandResponse(f"{setup.pair} {setup.direction} · {setup.state}", inline_keyboard([
            [("Details", f"sd:{setup.id}"), ("Why?", f"sw:{setup.id}")],
            [("← Setups", "m:setups"), ("Main menu", "m:root")],
        ]))

    def _stale_count(self, streams: dict) -> int:
        now = datetime.now(timezone.utc)
        stale = 0
        for (_, _, timeframe), timestamp in streams.items():
            aware = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
            unit, amount = timeframe[-1], int(timeframe[:-1])
            seconds = amount * {"m": 60, "h": 3600, "d": 86400}.get(unit, 60)
            stale += (now - aware).total_seconds() > seconds * self.settings.market_data_stale_multiplier
        return stale
