from __future__ import annotations

from models.permit_open_rule import PermitOpenRule
from models.ssh_key import SSHKey

FORCED_OPTIONS = [
    'command="echo Tunnel only;exit"',
    "no-agent-forwarding",
    "no-X11-forwarding",
    "no-pty",
]


def render_authorized_key_line(key: SSHKey, rules: list[PermitOpenRule]) -> str:
    permit_options = [f'permitopen="{rule.host}:{rule.port}"' for rule in rules if rule.enabled]
    options = FORCED_OPTIONS + permit_options
    return f"{','.join(options)} {key.public_key.strip()}"


def render_authorized_keys(keys: list[SSHKey]) -> str:
    lines: list[str] = []
    for key in keys:
        if not key.enabled:
            continue
        rules = [rule for rule in key.permit_rules if rule.enabled]
        if not rules:
            continue
        lines.append(render_authorized_key_line(key, rules))
    text = "\n".join(lines).strip()
    return f"{text}\n" if text else ""
