from __future__ import annotations

from models.ssh_key import SSHKey


def render_authorized_keys(keys: list[SSHKey]) -> str:
    """Plain authorized_keys lines without options or permitopen."""
    lines: list[str] = []
    for key in keys:
        if not key.enabled:
            continue
        line = key.public_key.strip()
        if line:
            lines.append(line)
    text = "\n".join(lines).strip()
    return f"{text}\n" if text else ""
