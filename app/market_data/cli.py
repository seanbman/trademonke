from __future__ import annotations

import argparse
import asyncio
import json

from app.settings import get_settings
from app.runtime import should_run_standalone_market_relay
from app.indicators.engine import IndicatorEngine
from app.liquidity.service import LiquidityMapService
from app.episodes.service import EpisodeEngine
from app.research.pipeline import ResearchPipeline
from app.setups.engine import SetupLifecycleEngine
from app.telemetry.db import SessionLocal

from .candidates import rank_candidates, save_candidate_evidence
from .collector import MarketDataCollector
from .exchange import ReadOnlyExchange
from .live import LiveMarketRelay
from .watchlist import (collection_symbols, enqueue_backfill, ensure_anchors,
                        normalize_symbol)
from app.telemetry.models import BackfillJobRecord, WatchlistAssetRecord


async def run(args) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        ensure_anchors(session, settings.market_symbols)
    async with ReadOnlyExchange(settings.market_data_exchange, settings.market_data_max_retries) as exchange:
        indicator_engine = IndicatorEngine(
            SessionLocal, settings.market_data_exchange, settings.strategy_version,
            settings.indicator_base_timeframe, settings.indicator_htfs,
            settings.indicator_ema_length, settings.indicator_structure_lookback,
            settings.indicator_smt_lookback, settings.indicator_pivot_lookback,
            settings.indicator_fvg_max_age)
        collector = MarketDataCollector(exchange, SessionLocal, settings.market_data_batch_limit,
                                        settings.candidate_quote, settings.candidate_min_quote_volume,
                                        settings.candidate_max_spread_bps, indicator_engine)
        collector.history_days = settings.market_data_history_days
        collector.strategy_version = settings.strategy_version
        collector.git_sha = settings.git_sha
        collector.setup_engine = SetupLifecycleEngine(
            SessionLocal, settings.market_data_exchange, settings.strategy_version, settings.git_sha,
            settings.setup_detection_min_score, settings.setup_expiry_candles)
        collector.liquidity_service = LiquidityMapService(
            SessionLocal, settings.market_data_exchange, settings.strategy_version,
            settings.git_sha, settings.liquidity_pivot_left, settings.liquidity_pivot_right,
            settings.liquidity_cluster_tolerance_bps,
            settings.liquidity_touch_tolerance_bps, settings.liquidity_expiry_candles)
        collector.episode_engine = EpisodeEngine(
            SessionLocal, settings.market_data_exchange, settings.strategy_version,
            settings.git_sha, settings.episode_displacement_body_bps)
        collector.research_pipeline = ResearchPipeline(SessionLocal, settings)
        if args.command == "backfill":
            for symbol in settings.market_symbols:
                for timeframe in settings.market_timeframes:
                    count = await collector.backfill(symbol, timeframe, settings.market_data_history_days)
                    print(json.dumps({"symbol": symbol, "timeframe": timeframe, "rows_processed": count}))
                print(json.dumps({"symbol": symbol, "supplemental": await collector.supplement(symbol.split("/")[0])}))
        elif args.command == "backfill-symbol":
            symbol = normalize_symbol(args.symbol)
            with SessionLocal() as session:
                asset = session.get(WatchlistAssetRecord, symbol)
                if asset is None or asset.status not in {"active", "probe"}:
                    raise SystemExit(f"{symbol} must be active or probe before targeted backfill")
                job = enqueue_backfill(session, exchange.exchange_id, symbol,
                                       tuple(args.timeframes.split(",")), args.days, "cli")
                session.commit()
                job_id = job.id
            await collector.process_backfill_job(job_id)
            with SessionLocal() as session:
                job = session.get(BackfillJobRecord, job_id)
                print(json.dumps({"job_id": job.id, "symbol": job.symbol, "status": job.status,
                                  "completed_timeframes": job.completed_timeframes,
                                  "rows_processed": job.rows_processed,
                                  "error_type": job.error_type}))
        elif args.command == "update":
            for symbol in settings.market_symbols:
                for timeframe in settings.market_timeframes:
                    count = await collector.update(symbol, timeframe)
                    print(json.dumps({"symbol": symbol, "timeframe": timeframe, "rows_processed": count}))
        elif args.command == "run":
            relay_task = None
            if should_run_standalone_market_relay(settings.market_stream_enabled):
                relay = LiveMarketRelay(
                    settings.market_symbols, settings.market_timeframes,
                    settings.market_stream_bind_host, settings.market_stream_port)
                relay_task = asyncio.create_task(relay.run_forever())
            try:
                await collector.run_forever(settings.market_timeframes, args.poll_seconds)
            finally:
                if relay_task is not None:
                    relay_task.cancel()
                    await asyncio.gather(relay_task, return_exceptions=True)
        elif args.command == "candidates":
            with SessionLocal() as session:
                current = collection_symbols(session)
            evidence = await rank_candidates(exchange, current, settings.candidate_quote,
                                             settings.candidate_min_quote_volume,
                                             settings.candidate_max_spread_bps, args.limit)
            with SessionLocal() as session:
                save_candidate_evidence(session, exchange.exchange_id, evidence)
            print(json.dumps([item.__dict__ for item in evidence], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only CCXT market-data research collector")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("backfill")
    symbol_parser = subparsers.add_parser("backfill-symbol")
    symbol_parser.add_argument("symbol")
    symbol_parser.add_argument("--days", type=int, default=365)
    symbol_parser.add_argument("--timeframes", default="5m,15m,30m,1h")
    subparsers.add_parser("update")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--poll-seconds", type=int, default=30)
    candidate_parser = subparsers.add_parser("candidates")
    candidate_parser.add_argument("--limit", type=int, default=10)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
