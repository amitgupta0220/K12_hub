VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
INSTALL_STAMP := $(VENV)/.installed

.PHONY: install format lint typecheck test integration-test migration-test verify infra-up infra-down infra-reset infra-logs infra-check db-upgrade db-downgrade db-current ingest-demo validate-demo dbt-debug dbt-run dbt-test dbt-build dbt-docs

install: $(INSTALL_STAMP)

$(INSTALL_STAMP): pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@touch $(INSTALL_STAMP)

format: install
	$(PYTHON) -m ruff format src tests scripts migrations
	$(PYTHON) -m ruff check --fix src tests scripts migrations

lint: install
	$(PYTHON) -m ruff format --check src tests scripts migrations
	$(PYTHON) -m ruff check src tests scripts migrations

typecheck: install
	$(PYTHON) -m mypy

test: install
	$(PYTHON) -m pytest -m "not integration"

integration-test: install
	$(PYTHON) -m pytest -m integration

migration-test: install
	$(PYTHON) -m pytest -m migration

verify: lint typecheck test

infra-up:
	docker compose up -d --wait postgres minio
	docker compose run --rm minio-init

infra-down:
	docker compose down

infra-reset:
	@printf "WARNING: This permanently deletes local PostgreSQL and MinIO volumes.\n"
	@printf "Type 'reset' to continue: "; read confirmation; \
		test "$$confirmation" = "reset" || { printf "Reset cancelled.\n"; exit 1; }
	docker compose down --volumes --remove-orphans

infra-logs:
	docker compose logs --follow postgres minio minio-init

infra-check: install
	$(PYTHON) scripts/check_services.py
	$(PYTHON) -m pytest -m integration

db-upgrade: install
	$(PYTHON) -m alembic upgrade head

db-downgrade: install
	$(PYTHON) -m alembic downgrade -1

db-current: install
	$(PYTHON) -m alembic current

ingest-demo: install
	$(PYTHON) -m k12hub.cli generate-data --seed 2026 --students 25 --school-year 2025-2026 --output-directory data/generated/ingest-demo
	$(PYTHON) -m k12hub.cli ingest --input-dir data/generated/ingest-demo/run-f57b686f98cfdb28 --source all

validate-demo: install
	$(PYTHON) -m k12hub.cli generate-data --seed 8800 --students 25 --school-year 2025-2026 --output-directory data/generated/validate-demo
	@output="$$($(PYTHON) -m k12hub.cli run-ingestion --input-dir data/generated/validate-demo/run-fade190e3f52284e)"; \
		printf "%s\n" "$$output"; \
		pipeline_run_id="$$(printf "%s\n" "$$output" | sed -n "s/.*pipeline_run_id=\\([^ ]*\\).*/\\1/p")"; \
		test -n "$$pipeline_run_id"; \
		$(PYTHON) -m k12hub.cli validate-data --pipeline-run-id "$$pipeline_run_id"

DBT := $(VENV)/bin/dbt
DBT_DIR := warehouse
DBT_ARGS := --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

dbt-debug: install
	@test -n "$$K12HUB_HASH_SALT" || { printf "K12HUB_HASH_SALT is required.\n"; exit 1; }
	$(DBT) debug $(DBT_ARGS)

dbt-run: install
	@test -n "$$K12HUB_HASH_SALT" || { printf "K12HUB_HASH_SALT is required.\n"; exit 1; }
	$(DBT) run $(DBT_ARGS)

dbt-test: install
	@test -n "$$K12HUB_HASH_SALT" || { printf "K12HUB_HASH_SALT is required.\n"; exit 1; }
	@test -n "$$K12HUB_EXPECTED_METRICS_PATH" || { printf "K12HUB_EXPECTED_METRICS_PATH is required.\n"; exit 1; }
	$(DBT) test $(DBT_ARGS) --vars "$$($(PYTHON) scripts/dbt_expected_metrics.py "$$K12HUB_EXPECTED_METRICS_PATH")"

dbt-build: install
	@test -n "$$K12HUB_HASH_SALT" || { printf "K12HUB_HASH_SALT is required.\n"; exit 1; }
	@test -n "$$K12HUB_EXPECTED_METRICS_PATH" || { printf "K12HUB_EXPECTED_METRICS_PATH is required.\n"; exit 1; }
	$(DBT) build $(DBT_ARGS) --vars "$$($(PYTHON) scripts/dbt_expected_metrics.py "$$K12HUB_EXPECTED_METRICS_PATH")"

dbt-docs: install
	@test -n "$$K12HUB_HASH_SALT" || { printf "K12HUB_HASH_SALT is required.\n"; exit 1; }
	@test -n "$$K12HUB_EXPECTED_METRICS_PATH" || { printf "K12HUB_EXPECTED_METRICS_PATH is required.\n"; exit 1; }
	$(DBT) docs generate $(DBT_ARGS) --vars "$$($(PYTHON) scripts/dbt_expected_metrics.py "$$K12HUB_EXPECTED_METRICS_PATH")"
