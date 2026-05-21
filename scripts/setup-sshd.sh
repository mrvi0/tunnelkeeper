#!/usr/bin/env bash
# One-time host setup for TunnelKeeper: sshd Include + generated snippets directory.
# Run on the Linux server (not WSL without openssh-server):
#   sudo ./scripts/setup-sshd.sh
# or: make setup-sshd

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "${ROOT}/.env"
  set +a
fi

SSHD_MAIN_CONFIG="${SSHD_MAIN_CONFIG:-/etc/ssh/sshd_config}"
SSHD_GENERATED_DIR="${SSHD_GENERATED_DIR:-/etc/ssh/sshd_config.d/generated}"
SSHD_INCLUDE_SNIPPET="${SSHD_INCLUDE_SNIPPET:-Include /etc/ssh/sshd_config.d/*.conf}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root. Try: sudo $0" >&2
  exit 1
fi

if [[ ! -f "${SSHD_MAIN_CONFIG}" ]]; then
  echo "Main sshd config not found: ${SSHD_MAIN_CONFIG}" >&2
  echo "Install OpenSSH server first, e.g.: apt install openssh-server" >&2
  exit 1
fi

mkdir -p "${SSHD_GENERATED_DIR}"
chmod 755 "$(dirname "${SSHD_GENERATED_DIR}")" "${SSHD_GENERATED_DIR}" 2>/dev/null || true

if grep -qE 'sshd_config\.d|/etc/ssh/sshd_config\.d/' "${SSHD_MAIN_CONFIG}"; then
  echo "Include for sshd_config.d already present in ${SSHD_MAIN_CONFIG}"
else
  echo "Adding to ${SSHD_MAIN_CONFIG}: ${SSHD_INCLUDE_SNIPPET}"
  printf '\n# TunnelKeeper / drop-in snippets\n%s\n' "${SSHD_INCLUDE_SNIPPET}" >> "${SSHD_MAIN_CONFIG}"
fi

echo "Generated snippets directory: ${SSHD_GENERATED_DIR}"

reload_ok=false
for unit in ssh sshd; do
  if systemctl reload "${unit}" 2>/dev/null; then
    echo "Reloaded: systemctl reload ${unit}"
    reload_ok=true
    break
  fi
done

if [[ "${reload_ok}" != true ]]; then
  if service ssh reload 2>/dev/null; then
    echo "Reloaded: service ssh reload"
  else
    echo "Warning: could not reload SSH automatically. Run: systemctl reload ssh" >&2
    exit 1
  fi
fi

echo "Done. Start TunnelKeeper with: sudo -E make run"
