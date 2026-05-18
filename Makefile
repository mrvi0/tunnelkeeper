VENV := .venv
ROOT := $(CURDIR)
export PYTHONPATH := $(ROOT)
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
ALEMBIC := $(VENV)/bin/alembic
RUFF := $(VENV)/bin/ruff

.PHONY: install run dev migrate lint format venv

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt

migrate: venv
	$(ALEMBIC) upgrade head

run: venv
	$(ALEMBIC) upgrade head
	$(UVICORN) app.main:app --host 127.0.0.1 --port 8080

dev: venv
	$(ALEMBIC) upgrade head
	$(UVICORN) app.main:app --host 127.0.0.1 --port 8080 --reload

lint: venv
	$(RUFF) check .

format: venv
	$(RUFF) format .
