.PHONY: install dev test lint fmt run attack

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 9090

run:
	uvicorn src.main:app --host 0.0.0.0 --port 9090 --workers 4

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/

attack:
	python -m tests.red_team.attack_simulation
