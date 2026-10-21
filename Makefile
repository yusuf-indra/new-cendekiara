.PHONY: install dev check schema
ROOT := $(CURDIR)
VENV := $(ROOT)/backend/.venv
PY := $(shell [ -x "$(VENV)/bin/python" ] && echo "$(VENV)/bin/python" || echo python3)

install:  ## set up backend venv (+ frontend deps once frontend/ exists)
	cd backend && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
	@if [ -d frontend ]; then cd frontend && npm ci; fi

dev:      ## run the backend locally (STORE=memory, AUTH_MODE=dev) + Vite dev server
	cd backend && $(PY) -m uvicorn cendekiara.api.app:app --reload --port 8080 & \
	if [ -d frontend ]; then cd frontend && npm run dev; fi

check:    ## exactly what CI runs; must pass before a merge
	cd backend && $(PY) -m ruff check . && $(PY) -m ruff format --check . && $(PY) -m mypy cendekiara && $(PY) -m pytest -q
	@if [ -d frontend ]; then cd frontend && npm run lint && npx tsc --noEmit && npx vitest run; \
	else echo "no frontend/ yet - skipping frontend checks (they arrive in Phase 5)"; fi

schema:   ## regenerate frontend/src/api/types.gen.ts from the command schemas
	cd backend && $(PY) -m cendekiara.cli commands list --json > ../frontend/src/api/commands.json
	cd frontend && npm run gen:types
