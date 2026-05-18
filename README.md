# TunnelKeeper

TunnelKeeper is a lightweight local-first web panel for managing tunnel-only SSH users through `authorized_keys` restrictions.

## MVP features

- Tunnel-only Linux user CRUD (`/usr/sbin/nologin`, no password)
- SSH key CRUD with validation and SHA256 fingerprint
- PermitOpen rule CRUD with enable/disable
- Automatic `authorized_keys` regeneration on every change
- Manual regenerate action from UI
- Temporary in-memory admin credentials generated on each startup
- Session-based auth, CSRF token, login rate limit, idle timeout
- Audit log for all mutating actions
- Optional readonly mode (`READONLY_MODE=true`)

## Stack

- Python 3.12
- FastAPI + Jinja2 + HTMX
- SQLAlchemy 2 + Alembic
- SQLite (default)
- TailwindCSS via CDN

## Quick start

1. Create virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies (creates `.venv` automatically if missing):

```bash
make install
```

3. Configure environment:

```bash
cp .env.example .env
```

4. Run app:

```bash
make run
```

On startup the app prints one-time credentials:

```text
================================================
TunnelKeeper Admin Panel
================================================
URL:      http://127.0.0.1:8080
Login:    admin_xxxxx
Password: yyyyyyyyyyyy
================================================
```

Credentials are stored only in memory and become invalid after process stop.

Readonly mode example:

```bash
READONLY_MODE=true make run
```

## Make targets

- `make install` - install dependencies
- `make run` - run locally on `127.0.0.1:8080`
- `make dev` - run with reload
- `make migrate` - run alembic migrations
- `make lint` - run ruff checks
- `make format` - format code with ruff

## Linux integration notes

Mutating operations may require root permissions:

- `useradd` for Linux user creation
- home `.ssh` and `authorized_keys` permission management
- writing into user home directories

If app is started without required permissions, database changes are rolled back and a readable error is shown in UI.

## Operational model

TunnelKeeper is designed as an ephemeral admin tool:

1. Start panel (`make run`)
2. Apply access changes
3. Stop panel

It is not intended to be permanently internet-exposed.
