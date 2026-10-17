.PHONY: install lint types test check bench demo trial

PY ?= python3

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

types:
	mypy

test:
	$(PY) -m pytest --cov=pawl --cov-report=term

check: lint types test

# Writes BENCHMARKS.md and benchmarks/results.json. Commit both.
bench:
	$(PY) -m benchmarks run

trial:
	$(PY) -m benchmarks.trial

demo:
	examples/run_demo.sh
