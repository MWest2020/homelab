#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: entrypoint
#
# scripts/docs-freshness-agent.sh — houdt de Docusaurus-docs synchroon via een Claude-agent.
#
# Draait op agent-lxc (cron/systemd-timer). Pullt de repo, berekent de wijzigingen sinds de
# laatste docs-update, laat `claude` headless de docs onder `docusaurus/` bijwerken, en commit
# direct op main (trunk-based). Claude krijgt alleen edit-rechten; git doet deze wrapper, zodat
# de agent geen shell-toegang nodig heeft. Twee scrub-lagen: de prompt (nooit 100.x/secrets) én
# een harde grep-gate in de wrapper die commit+push blokkeert bij een leak.
#
# Writes: commits op main (origin), alleen bij doc-wijzigingen die de scrub-gate passeren.
# Idempotent: yes (geen wijziging -> geen PR, branch opgeruimd).
# Requires: claude (auth), git, gh (auth), een homelab-clone in $REPO_DIR.
#
# Usage:
#   ./scripts/docs-freshness-agent.sh
#   # crontab (agent-lxc), wekelijks ma 03:00:
#   0 3 * * 1 /home/agent/homelab/scripts/docs-freshness-agent.sh >> /home/agent/docs-agent.log 2>&1

set -euo pipefail

readonly REPO_DIR="${REPO_DIR:-${HOME}/homelab}"
readonly CLAUDE="${CLAUDE_BIN:-${HOME}/.npm-global/bin/claude}"
readonly PROMPT_FILE="${REPO_DIR}/scripts/docs-freshness-prompt.md"
readonly BASE_BRANCH="main"

main() {
  cd "${REPO_DIR}"
  git fetch -q origin
  git checkout -q "${BASE_BRANCH}"
  git pull -q --ff-only origin "${BASE_BRANCH}"

  # Referentiepunt = laatste commit die docs raakte; context = commits sindsdien.
  local last_docs_commit context
  last_docs_commit="$(git log -1 --format=%H -- docusaurus/ 2>/dev/null || true)"
  if [[ -n "${last_docs_commit}" ]]; then
    context="$(git log --oneline "${last_docs_commit}..HEAD" 2>/dev/null | head -40)"
  else
    context="$(git log --oneline -40)"
  fi

  if [[ -z "${context}" ]]; then
    echo "geen wijzigingen sinds laatste docs-update; niets te doen."
    exit 0
  fi

  # Trunk-based: direct op main. Claude headless: alleen edits (acceptEdits); geen Bash
  # nodig (context wordt meegegeven).
  printf '%s\n\n## Recente repo-wijzigingen (context):\n%s\n' \
    "$(cat "${PROMPT_FILE}")" "${context}" \
    | "${CLAUDE}" -p --permission-mode acceptEdits

  if git diff --quiet -- docusaurus/; then
    echo "agent maakte geen doc-wijzigingen."
    exit 0
  fi

  git add docusaurus/

  # HARDE scrub-gate (deterministisch, los van de prompt): blokkeer commit/push als er
  # een Tailscale-IP, token of secret in de docs-diff staat. Vangnet zonder PR-review.
  if git diff --cached -- docusaurus/ \
      | grep -qE '100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}|tskey-[A-Za-z0-9]|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'; then
    echo "ABORT: scrub-gate vond gevoelige data (Tailscale-IP/token/secret) in de docs-diff." >&2
    git reset -q
    exit 1
  fi

  git commit -q -m "docs: auto-update via freshness-agent ($(date +%F))"
  git push -q origin "${BASE_BRANCH}"
  echo "naar ${BASE_BRANCH} gepusht."
}

main "$@"
