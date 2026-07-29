VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

.PHONY: install format lint typecheck test integration-test verify infra-up infra-down infra-reset infra-logs infra-check

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

format: install
	$(PYTHON) -m ruff format src tests scripts
	$(PYTHON) -m ruff check --fix src tests scripts

lint: install
	$(PYTHON) -m ruff format --check src tests scripts
	$(PYTHON) -m ruff check src tests scripts

typecheck: install
	$(PYTHON) -m mypy

test: install
	$(PYTHON) -m pytest -m "not integration"

integration-test: install
	$(PYTHON) -m pytest -m integration

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
