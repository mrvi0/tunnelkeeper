VENV := .venv
ROOT := $(CURDIR)
export PYTHONPATH := $(ROOT)

# Load APP_HOST / APP_PORT from .env when present
ifneq (,$(wildcard .env))
include .env
export
endif
APP_HOST ?= 127.0.0.1
APP_PORT ?= 8080

PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
ALEMBIC := $(VENV)/bin/alembic
RUFF := $(VENV)/bin/ruff

.PHONY: install run dev migrate lint format venv setup-sshd

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt

migrate: venv
	$(ALEMBIC) upgrade head

run: venv
	$(ALEMBIC) upgrade head
	$(UVICORN) app.main:app --host $(APP_HOST) --port $(APP_PORT)

dev: venv
	$(ALEMBIC) upgrade head
	$(UVICORN) app.main:app --host $(APP_HOST) --port $(APP_PORT) --reload

lint: venv
	$(RUFF) check .

format: venv
	$(RUFF) format .

setup-sshd:
	sudo bash scripts/setup-sshd.sh
