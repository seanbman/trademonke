# Deployment and persistence

Copy `.env.example` to `.env`, generate a strong PostgreSQL password, then create host paths. For a private server use `DATA_ROOT=/opt/trading-platform/data`, `LOG_ROOT=/opt/trading-platform/logs`, and `BACKUP_ROOT=/opt/trading-platform/backups`.

```bash
sudo install -d -m 0750 -o "$USER" -g docker /opt/trading-platform/{data/{postgres,freqtrade,platform},backups,logs/{freqtrade,platform}}
docker compose config
docker compose run --rm migrate
docker compose up -d platform-api
curl http://127.0.0.1:8000/health
```

Containers are disposable; bind mounts hold irreplaceable state. `docker compose down` preserves it, but `docker compose down -v` may remove Docker-managed volumes and should be treated as destructive. Never commit data, logs, dumps, or secrets.

Database changes are applied by the one-shot `migrate` service before application services start. Applied filenames and SHA-256 checksums are stored in `schema_migrations`; changing an applied SQL file fails closed. Before upgrading an existing deployment, stop writers, take a verified backup, run `docker compose run --rm migrate`, and only then restart the application services.

`/health` reports the persisted pause and kill controls, database connectivity, feed freshness, current service heartbeats, strategy version, and Git SHA. An empty or stale feed, or a heartbeat older than two minutes, produces `status=degraded` rather than a false healthy result.

Back up with `BACKUP_ROOT=/opt/trading-platform/backups scripts/backup_postgres.sh`. A daily cron example is `15 2 * * * cd /opt/trading-platform/app && /usr/bin/env BACKUP_ROOT=/opt/trading-platform/backups ./scripts/backup_postgres.sh`. Retention defaults to 14 days.

Verify restoration quarterly on an isolated database/server: start PostgreSQL, restore a selected dump with `scripts/restore_postgres.sh`, compare setup/event counts and newest timestamps, then call `/health` and `/setups`. Never test restore by overwriting the only production database.

To migrate: stop writers, make and checksum a final dump, rsync the repository plus data/freqtrade and backup archives over an encrypted channel, recreate ownership, restore PostgreSQL, update `.env`, validate Compose, and start services. Keep the old host read-only until counts and a dry-run smoke test agree. Ensure chrony/systemd-timesyncd reports synchronized UTC time.

## Heroku (relay-only GUI)

Heroku runs a single `web` dyno in `PLATFORM_MODE=relay`. It serves the static React GUI, authenticates browser sessions, and caches workstation snapshots pushed from your local machine. It does **not** collect market data, run detection, or retain long-term candle history.

Prerequisites:

```bash
heroku login
heroku create your-app-name
heroku addons:create heroku-postgresql:essential-0
heroku buildpacks:add --index 1 heroku/nodejs
heroku buildpacks:add --index 2 heroku/python
heroku config:set PLATFORM_MODE=relay
heroku config:set PLATFORM_GUI_ACCESS_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
heroku config:set PLATFORM_FEEDER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
heroku config:set PLATFORM_DRY_RUN=true PLATFORM_TRADING_MODE=spot PLATFORM_EXECUTION_MODE=disabled
git push heroku main
heroku ps:scale web=1 worker=0
```

Open `https://your-app-name.herokuapp.com/`, paste the GUI token, and start the local brain (below). When the local `relay-agent` is connected, the GUI shows live workstation snapshots. When it is offline, the remote serves cached snapshots from the last 24 hours with a simplified chart.

`app.json` provides a deploy template with the same defaults. Freqtrade and Telegram are not started on Heroku; keep execution disabled and use the private Docker stack when those services are required.

Heroku applies `.slugignore` before buildpacks run, so do not list GUI source files (`gui/package.json`, `gui/src/`, etc.) there or the Node postbuild step cannot compile the workstation.

## Local brain workflow

Seed local PostgreSQL from the legacy `platform.db` once, then run collection and relay outbound to Heroku:

```bash
docker compose up -d postgres
docker compose run --rm migrate
python scripts/import_platform_db.py
docker compose up -d platform-api market-data
relay-agent
```

Local `.env` should keep `PLATFORM_MODE=full` and set:

```bash
PLATFORM_REMOTE_RELAY_URL=wss://your-app-name.herokuapp.com/api/v1/relay/ws
PLATFORM_FEEDER_TOKEN=<same value as Heroku PLATFORM_FEEDER_TOKEN>
```

Or use `make start-local-brain` after configuring the relay URL and feeder token.
