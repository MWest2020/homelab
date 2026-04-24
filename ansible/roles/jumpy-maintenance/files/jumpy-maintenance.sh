#!/usr/bin/env bash
# Weekly jumpy maintenance. Idempotent — safe to re-run.
# Invoked by jumpy-maintenance.service (systemd timer, Sunday 04:00).

set -uo pipefail

LOG=/var/log/jumpy-maintenance.log
exec >>"$LOG" 2>&1

echo
echo "=== jumpy-maintenance $(date --iso-8601=seconds) ==="
df -h / | tail -1

echo "--- apt autoremove + clean ---"
DEBIAN_FRONTEND=noninteractive apt-get autoremove --purge -y
apt-get clean

echo "--- journald vacuum (200M) ---"
journalctl --vacuum-size=200M

echo "--- prune rotated logs older than 30d ---"
find /var/log -type f -name "*.gz" -mtime +30 -print -delete

echo "--- go build cache (user jump, if go present) ---"
if runuser -u jump -- sh -c 'command -v go >/dev/null 2>&1'; then
  runuser -u jump -- sh -c 'go clean -cache' || true
else
  echo "go not in jump's PATH — skip"
fi

echo "--- final df ---"
df -h / | tail -1

echo "=== done ==="
