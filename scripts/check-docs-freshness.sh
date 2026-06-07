#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: tool
#
# scripts/check-docs-freshness.sh — waarschuw als infra wijzigt zonder docs-wijziging.
#
# Vergelijkt de staged wijzigingen: raakt een commit `terraform/`, `ansible/` of
# `kubernetes/` aan zónder iets onder `docusaurus/`, dan kan de documentatie verouderd
# raken. Dit is een NUDGE (exit 0 + waarschuwing naar stderr), geen blokkade — bedoeld
# als pre-commit-hook of CI-stap. De freshness-agent op agent-lxc doet het echte werk;
# dit maakt drift zichtbaar.
#
# Writes: read-only (leest git-index).
# Idempotent: yes.
# Requires: git, een git-repo.
#
# Usage:
#   ./scripts/check-docs-freshness.sh                 # checkt staged files (pre-commit)
#   ./scripts/check-docs-freshness.sh --range A..B    # checkt een commit-range (CI)

set -euo pipefail

readonly INFRA_PATHS='^(terraform|ansible|kubernetes)/'
readonly DOCS_PATH='^docusaurus/'

main() {
  local changed
  if [[ "${1:-}" == "--range" && -n "${2:-}" ]]; then
    changed="$(git diff --name-only "$2")"
  else
    changed="$(git diff --cached --name-only)"
  fi

  if [[ -z "${changed}" ]]; then
    exit 0
  fi

  if grep -qE "${INFRA_PATHS}" <<<"${changed}" && ! grep -qE "${DOCS_PATH}" <<<"${changed}"; then
    echo "waarschuwing: infra gewijzigd zonder docs-wijziging (docusaurus/)." >&2
    echo "  -> overweeg de docs bij te werken, of laat de freshness-agent op agent-lxc een PR maken." >&2
  fi

  exit 0
}

main "$@"
