.PHONY: test lint fmt

test:
	python -m pytest -q

lint:
	ruff check comms tests scripts

fmt:
	ruff format comms tests scripts
