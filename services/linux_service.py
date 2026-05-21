from __future__ import annotations

import logging
import os
import pwd
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.config import get_settings
from models.tunnel_user import TunnelUser
from services.exceptions import LinuxOperationError

logger = logging.getLogger(__name__)


class LinuxService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _resolve_home(self, linux_home: str) -> Path:
        home = Path(linux_home).expanduser().resolve()
        if not home.is_absolute() or home in (Path("/"), Path("/home"), Path("/root")):
            raise LinuxOperationError(f"Refusing to operate on unsafe home path: {linux_home}")
        if len(home.parts) < 2:
            raise LinuxOperationError(f"Refusing to operate on unsafe home path: {linux_home}")
        return home

    def create_linux_user(self, user: TunnelUser) -> None:
        cmd = ["useradd", "-m", "-d", user.linux_home, "-s", user.linux_shell, user.username]
        if user.supplementary_groups.strip():
            cmd.insert(-1, "-G")
            cmd.insert(-1, user.supplementary_groups.strip())
        logger.info("Creating linux user %s: %s", user.username, " ".join(cmd))
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0 and "already exists" not in completed.stderr.lower():
            raise LinuxOperationError(f"Failed to create linux user: {completed.stderr.strip()}")

    def update_linux_user(self, user: TunnelUser) -> None:
        cmd = ["usermod", "-d", user.linux_home, "-s", user.linux_shell]
        if user.supplementary_groups.strip():
            cmd.extend(["-G", user.supplementary_groups.strip()])
        else:
            cmd.append("-G")
            cmd.append("")
        cmd.append(user.username)
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise LinuxOperationError(f"Failed to update linux user: {completed.stderr.strip()}")

    def delete_linux_user(self, user: TunnelUser) -> None:
        home = self._resolve_home(user.linux_home)
        logger.info("Deleting linux user %s", user.username)
        completed = subprocess.run(
            ["userdel", "-r", user.username],
            capture_output=True,
            text=True,
            check=False,
        )
        stderr = completed.stderr.strip().lower()
        if completed.returncode != 0 and "does not exist" not in stderr and "not found" not in stderr:
            logger.warning("userdel failed for %s: %s", user.username, completed.stderr.strip())
        if home.exists():
            try:
                shutil.rmtree(home)
            except OSError as exc:
                raise LinuxOperationError(f"Failed to remove home {home}: {exc}") from exc
        self.delete_sshd_config(user)

    def ensure_ssh_directory(self, user: TunnelUser) -> tuple[Path, Path]:
        home = self._resolve_home(user.linux_home)
        ssh_dir = home / ".ssh"
        auth_keys = ssh_dir / "authorized_keys"
        try:
            ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            auth_keys.touch(mode=0o600, exist_ok=True)
            os.chmod(ssh_dir, 0o700)
            os.chmod(auth_keys, 0o600)
            self._chown_tree(home, user.username)
        except OSError as exc:
            raise LinuxOperationError(f"Failed to prepare SSH directory: {exc}") from exc
        return ssh_dir, auth_keys

    def _chown_tree(self, path: Path, username: str) -> None:
        try:
            pw = pwd.getpwnam(username)
            os.chown(path, pw.pw_uid, pw.pw_gid)
            for root, dirs, files in os.walk(path):
                os.chown(root, pw.pw_uid, pw.pw_gid)
                for d in dirs:
                    os.chown(os.path.join(root, d), pw.pw_uid, pw.pw_gid)
                for f in files:
                    os.chown(os.path.join(root, f), pw.pw_uid, pw.pw_gid)
        except KeyError:
            logger.warning("User %s not found in passwd for chown", username)

    def sshd_config_path(self, user: TunnelUser) -> Path:
        return Path(self.settings.sshd_generated_dir) / user.sshd_config_filename

    def delete_sshd_config(self, user: TunnelUser) -> None:
        path = self.sshd_config_path(user)
        if path.exists():
            backup = self.backup_file(path)
            path.unlink()
            logger.info("Removed sshd config %s backup=%s", path, backup)

    def backup_file(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        return backup_path

    def atomic_write(self, target: Path, content: str, mode: int = 0o644) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=str(target.parent), delete=False) as temp:
            temp.write(content)
            temp_path = Path(temp.name)
        os.chmod(temp_path, mode)
        temp_path.replace(target)

    def check_sshd_include(self) -> str | None:
        main = Path(self.settings.sshd_main_config)
        if not main.exists():
            return f"Main sshd config not found: {main}"
        text = main.read_text(encoding="utf-8", errors="replace")
        snippet = self.settings.sshd_include_snippet.strip()
        if snippet and snippet not in text:
            return (
                f"Add this line to {main}:\n  {snippet}\n"
                "Then run: systemctl reload sshd"
            )
        return None

    def reload_sshd(self) -> None:
        if not self.settings.sshd_reload_on_change:
            logger.info("SSHD reload skipped (SSHD_RELOAD_ON_CHANGE=false)")
            return
        for cmd in (
            ["systemctl", "reload", "ssh"],
            ["systemctl", "reload", "sshd"],
            ["service", "ssh", "reload"],
        ):
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode == 0:
                logger.info("Reloaded SSH via %s", " ".join(cmd))
                return
        raise LinuxOperationError(
            "Failed to reload SSH service. Run manually: systemctl reload sshd"
        )
