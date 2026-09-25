# Samjha — developer commands.
# Windows users without `make`: run the equivalent commands from README "Setup" (they are one-liners),
# or use Git Bash / WSL.

PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || ([ -x .venv/Scripts/python.exe ] && echo .venv/Scripts/python.exe || echo python))

.PHONY: install dev api web test test-engine test-api lint eval seed lexicon-review

install:
	$(PY) -m pip install -e "engine[dev]" -e "api[dev]"
	cd web && npm install

api:
	cd api && $(PY) -m uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

# runs api + web together (Ctrl+C stops both)
dev:
	@$(MAKE) -j2 api web

test: test-engine test-api

test-engine:
	cd engine && $(PY) -m pytest -q

test-api:
	cd api && $(PY) -m pytest -q

lint:
	$(PY) -m ruff check engine api eval
	cd web && npm run lint

# expand templates -> run engine -> (optional) Gemini baseline -> metrics -> results/latest.json
eval:
	$(PY) eval/generate.py
	$(PY) eval/run_engine.py
	$(PY) eval/run_baseline.py
	$(PY) eval/metrics.py
	$(PY) eval/update_readme.py

# load demo scenarios into the running API's database
seed:
	$(PY) -c "import httpx; print(httpx.post('http://localhost:8000/demo/seed').json())"

lexicon-review:
	$(PY) engine/tools/make_lexicon_review.py
