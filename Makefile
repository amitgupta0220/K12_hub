VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

.PHONY: install format lint typecheck test verify

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

format: install
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

lint: install
	$(PYTHON) -m ruff format --check src tests
	$(PYTHON) -m ruff check src tests

typecheck: install
	$(PYTHON) -m mypy

test: install
	$(PYTHON) -m pytest

verify: lint typecheck test
