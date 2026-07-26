COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif docker-compose version >/dev/null 2>&1; then echo "docker-compose"; fi)

.PHONY: run start start-local-brain feed-heroku start-telegram gui-token rotate-gui-token verify-gui-stream test lint api compose-check strategy-check migrate research-baseline data-backfill data-update candidates telegram deb
run: start

deb:
	@bash scripts/desktop/build-deb.sh

start:
	@test -f .env || (echo "missing .env; create it without overwriting any existing secrets"; exit 2)
	@.venv/bin/python scripts/prepare_env.py
	@test -n "$(COMPOSE)" || (echo "Docker Compose is unavailable; install the Compose plugin or docker-compose"; exit 2)
	@docker info >/dev/null 2>&1 || (echo "Cannot access the Docker daemon."; echo "Start Docker, then grant this user access: sudo usermod -aG docker \"$$USER\""; echo "Log out and back in (or run: newgrp docker), then retry make run."; exit 2)
	@$(COMPOSE) config >/dev/null
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d platform-api research-gui market-data
	@.venv/bin/python scripts/verify_stack.py

start-local-brain:
	@test -f .env || (echo "missing .env; create it without overwriting any existing secrets"; exit 2)
	@test -f platform.db || (echo "missing platform.db for one-time import"; exit 2)
	@.venv/bin/python scripts/prepare_env.py
	@test -n "$(COMPOSE)" || (echo "Docker Compose is unavailable"; exit 2)
	@docker info >/dev/null 2>&1 || (echo "Cannot access the Docker daemon"; exit 2)
	@$(COMPOSE) config >/dev/null
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm migrate
	@test -f .platform-db-imported || ( \
	  $(COMPOSE) build platform-api && \
	  $(COMPOSE) run --rm --no-deps \
	    -v "$(PWD)/platform.db:/app/platform.db:ro" \
	    --entrypoint python platform-api scripts/import_platform_db.py && \
	  touch .platform-db-imported )
	$(COMPOSE) up -d market-data relay-agent
	@echo "Feeding Heroku. Open https://bman-experiments-c0fe4f7ff667.herokuapp.com/"

feed-heroku: start-local-brain

start-telegram:
	@test -f .env || (echo "missing .env"; exit 2)
	@test -n "$(COMPOSE)" || (echo "Docker Compose is unavailable"; exit 2)
	@docker info >/dev/null 2>&1 || (echo "Cannot access the Docker daemon"; exit 2)
	$(COMPOSE) up -d --build telegram-bot

gui-token:
	@.venv/bin/python scripts/prepare_env.py --print-gui-token

rotate-gui-token:
	@.venv/bin/python scripts/prepare_env.py --rotate-gui-token

verify-gui-stream:
	@.venv/bin/python scripts/verify_gui_websocket.py

test:
	.venv/bin/python -m pytest
lint:
	.venv/bin/python -m ruff check app tests user_data/strategies
api:
	python3 -m uvicorn app.api.main:app --reload
compose-check:
	docker compose --env-file .env.example config -q
strategy-check:
	docker compose run --rm freqtrade list-strategies --config /freqtrade/user_data/config/config.dryrun.json
migrate:
	.venv/bin/python -m app.telemetry.migrations
research-baseline:
	.venv/bin/python -m app.research.cli baseline
data-backfill:
	.venv/bin/market-data backfill
data-update:
	.venv/bin/market-data update
candidates:
	.venv/bin/market-data candidates
backfill-symbol:
	@test -n "$(SYMBOL)" || (echo "usage: make backfill-symbol SYMBOL=SOL/USDT"; exit 2)
	.venv/bin/market-data backfill-symbol "$(SYMBOL)" --days "$${DAYS:-365}"
telegram:
	.venv/bin/telegram-bot
