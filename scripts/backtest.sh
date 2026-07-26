#!/usr/bin/env bash
set -euo pipefail
timerange="${1:?usage: $0 YYYYMMDD-YYYYMMDD}"
docker compose run --rm freqtrade backtesting --config /freqtrade/user_data/config/config.dryrun.json --strategy FvgProEliteStrategy --timerange "$timerange" --fee 0.0026

