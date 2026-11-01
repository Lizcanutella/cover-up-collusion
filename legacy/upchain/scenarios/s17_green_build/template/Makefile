PY ?= python3

.PHONY: dev test lint fmt clean

dev:
	$(PY) -m venv .venv && .venv/bin/pip install -r requirements.txt -e '.[dev]'

test:
	$(PY) -m pytest -q

lint:
	ruff check . && ruff format --check .

fmt:
	ruff format . && ruff check --fix .

clean:
	rm -rf .venv .pytest_cache .ruff_cache build *.egg-info
