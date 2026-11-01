PY ?= python3.12
VENV ?= .venv
BIN = $(VENV)/bin

.PHONY: install test lint seed job clean

install:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q -e '.[dev]'

test:
	$(BIN)/python -m pytest -q

lint:
	$(BIN)/ruff check casework tests
	$(BIN)/ruff format --check casework tests

seed:
	$(BIN)/python scripts/seed_dev_db.py casework-dev.db tests/fixtures/tickets.json

job:
	@test -n "$(NAME)" || (echo "usage: make job NAME=<job>" && exit 1)
	$(BIN)/python -c "import sys; from casework.jobs import scheduler; sys.exit(scheduler.run_one('$(NAME)'))"

clean:
	rm -rf $(VENV) .pytest_cache casework-dev.db
