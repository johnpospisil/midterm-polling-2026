.PHONY: all ingest build models figures report test lint

all: ingest build models figures report

ingest:
	uv run python -m mp.ingest

build:
	uv run python -m mp.build

models:
	uv run python -m mp.models

figures:
	uv run python -m mp.viz

report:
	quarto render report

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
