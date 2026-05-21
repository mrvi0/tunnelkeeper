# TunnelKeeper

TunnelKeeper is a lightweight local-first web panel for managing tunnel-only SSH users on a Linux host.

## Architecture

Each developer gets a dedicated Linux user (for example `tunnel-vital`):

- **Plain** `~/.ssh/authorized_keys` — only `ssh-ed25519 AAAA...` lines, no `permitopen` in keys
- **ACL** in `/etc/ssh/sshd_config.d/generated/<username>.conf` via `Match User` + `PermitOpen`
- Optional shell, supplementary groups (`docker`, …), and tunnel-only vs interactive login

Workflow:

1. Add **Destinations** (global host:port catalog)
2. Create a **tunnel user**, pick destinations and SSH options
3. Add **SSH keys** on the user page
4. Panel writes `authorized_keys` + sshd snippet and runs `systemctl reload sshd`

### sshd prerequisite (one-time on the server)

```bash
sudo ./scripts/setup-sshd.sh
# or
make setup-sshd
```

This creates `/etc/ssh/sshd_config.d/generated/`, appends `Include /etc/ssh/sshd_config.d/*.conf` to the main config if missing, and reloads sshd.

The dashboard warns if the main config is missing (common on WSL without `openssh-server`).

## Features

- Tunnel user CRUD with shell, groups, sshd Match options
- Global destinations + per-user PermitOpen assignment
- SSH key CRUD per user (plain keys)
- Automatic provisioning on every change
- Manual regenerate from user page
- Ephemeral admin credentials on each startup
- Session auth, CSRF, login rate limit, idle timeout
- Audit log, optional readonly mode

## Stack

- Python 3.12, FastAPI, Jinja2, HTMX
- SQLAlchemy 2 + Alembic, SQLite (default)
- TailwindCSS via CDN

## Quick start

```bash
make install
cp .env.example .env
make migrate
make run
```

On startup the app prints one-time admin credentials (memory only, invalid after stop).

### Remote access

```env
APP_HOST=0.0.0.0
APP_PORT=8080
```

Open the firewall if needed. Do not leave the panel exposed without TLS and network restrictions.

## Make targets

- `make install` — dependencies
- `make run` — `APP_HOST` / `APP_PORT` from `.env`
- `make dev` — reload
- `make migrate` — Alembic
- `make lint` / `make format` — ruff

## How sshd configs combine

`sshd` reads `/etc/ssh/sshd_config` from top to bottom. When it hits `Include /etc/ssh/sshd_config.d/*.conf`, it loads every `*.conf` in that directory (alphabetically), then continues the main file.

TunnelKeeper writes only **per-user snippets**, e.g. `/etc/ssh/sshd_config.d/generated/tunnel-vital.conf`:

```text
Match User tunnel-vital
    AllowTcpForwarding yes
    PermitOpen 10.0.0.5:5432
    ...
```

`Match User` applies **only when someone logs in as that Linux user**. It is not “more privileged” than the main config — it **narrows** what that user may do (allowed forward targets, no TTY, ForceCommand, etc.). Everyone else keeps the global rules from the main file.

At login time sshd merges: global defaults → matching `Match` blocks for that user. For the same keyword, more specific `Match` rules for that session usually win over generic globals.

The main `sshd_config` is **never** auto-generated; only the snippet files under `SSHD_GENERATED_DIR` are.

## Linux integration

Mutating operations typically require **root**:

- `useradd` / `usermod` / `userdel`
- `~/.ssh/authorized_keys` and ownership
- `/etc/ssh/sshd_config.d/generated/*.conf`
- `systemctl reload sshd` (when `SSHD_RELOAD_ON_CHANGE=true`)

Without permissions, DB changes roll back and the UI shows an error.

## Operational model

Ephemeral admin tool: start → apply changes → stop. Not meant to stay internet-facing permanently.
