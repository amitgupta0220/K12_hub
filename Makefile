VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

.PHONY: install format lint typecheck test integration-test migration-test verify infra-up infra-down infra-reset infra-logs infra-check db-upgrade db-downgrade db-current

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

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
