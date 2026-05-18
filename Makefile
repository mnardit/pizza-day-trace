.PHONY: setup all smoke trace anchor jercos analyze test clean clean-cache

PY ?= .venv/bin/python

setup:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements.txt

# Full pipeline that regenerates every committed artifact in data/processed/
all: trace anchor jercos analyze

smoke:
	$(PY) -m src.run_trace --depth 2 --out-suffix=-smoke

trace:
	$(PY) -m src.run_trace --depth 5

anchor:
	$(PY) -m src.run_anchor

jercos:
	$(PY) -m src.run_jercos

analyze:
	$(PY) -m src.run_analyze

test:
	$(PY) -m pytest -q tests/

clean-cache:
	rm -f data/cache.sqlite

clean:
	rm -rf data/processed/*.csv data/processed/*.json
