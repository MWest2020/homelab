#!/usr/bin/env bash
# Entry point for the systemd units and for manual runs:
#   run.sh collect            pull log lines into the cache (every 3 h)
#   run.sh report [--skip x]  the weekly report (Sunday night)
# Scanners each run in their own memory-capped scope (secreport/util.py:capped).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
export PATH="$HOME/.local/bin:$PATH"
if [[ ${1:-} == report ]]; then
  ./install-scanners.sh >/dev/null   # idempotent; pinned versions, sha256-checked
fi
exec nice -n 10 uv run --frozen --no-dev secreport "$@"
