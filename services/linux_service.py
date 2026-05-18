from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from models.tunnel_user import TunnelUser
from services.exceptions import LinuxOperationError

logger = logging.getLogger(__name__)


class LinuxService:
    def create_linux_user(self, username: str, linux_home: str) -> None:
        cmd = [
            "useradd",
            "-m",
            "-d",
            linux_home,
            "-s",
            "/usr/sbin/nologin",
            username,
        ]
        logger.info("Creating linux tunnel user %s", username)
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0 and "already exists" not in completed.stderr.lower():
            raise LinuxOperationError(f"Failed to create linux user: {completed.stderr.strip()}")

    def ensure_ssh_directory(self, user: TunnelUser) -> tuple[Path, Path]:
        home = Path(user.linux_home).expanduser()
        ssh_dir = home / ".ssh"
        auth_keys = ssh_dir / "authorized_keys"
        try:
            ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            auth_keys.touch(mode=0o600, exist_ok=True)
            os.chmod(ssh_dir, 0o700)
            os.chmod(auth_keys, 0o600)
        except OSError as exc:
            raise LinuxOperationError(f"Failed to prepare SSH directory: {exc}") from exc
        return ssh_dir, auth_keys

    def backup_file(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        return backup_path

    def atomic_write(self, target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=str(target.parent), delete=False) as temp:
            temp.write(content)
            temp_path = Path(temp.name)
        os.chmod(temp_path, 0o600)
        temp_path.replace(target)
