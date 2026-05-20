from __future__ import annotations

from models.permit_open_rule import PermitOpenRule
from models.ssh_key import SSHKey

FORCED_OPTIONS = [
    'command="echo Tunnel only;exit"',
    "no-agent-forwarding",
    "no-X11-forwarding",
    "no-pty",
]


def render_authorized_key_line(public_key: str, rules: list[PermitOpenRule]) -> str:
    permit_options = [f'permitopen="{rule.host}:{rule.port}"' for rule in rules if rule.enabled]
    options = FORCED_OPTIONS + permit_options
    return f"{','.join(options)} {public_key.strip()}"


def render_authorized_keys_for_user(
    keys: list[SSHKey],
    tunnel_user_id: int,
    rules_by_key: dict[int, list[PermitOpenRule]],
) -> str:
    lines: list[str] = []
    for key in keys:
        if not key.enabled:
            continue
        rules = rules_by_key.get(key.id, [])
        enabled_rules = [rule for rule in rules if rule.enabled]
        if not enabled_rules:
            continue
        lines.append(render_authorized_key_line(key.public_key, enabled_rules))
    text = "\n".join(lines).strip()
    return f"{text}\n" if text else ""
