#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: entrypoint
#
# scripts/docs-freshness-agent.sh — houdt de Docusaurus-docs synchroon via een Claude-agent.
#
# Draait op agent-lxc (cron/systemd-timer). Pullt de repo, berekent de wijzigingen sinds de
# laatste docs-update, laat `claude` headless de docs onder `docusaurus/` bijwerken, en opent
# een PR via `gh` (nooit direct naar main — mens reviewt). Claude krijgt alleen edit-rechten;
# git/gh doet deze wrapper, zodat de agent geen shell-toegang nodig heeft. Scrub-policy zit in
# de prompt (nooit Tailscale-100.x/secrets in de docs).
#
# Writes: een docs/*-branch + PR op origin (alleen bij wijzigingen).
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

  local branch="docs/auto-$(date +%Y%m%d-%H%M%S)"
  git checkout -q -b "${branch}"

  # Claude headless: alleen edits (acceptEdits); geen Bash nodig (context wordt meegegeven).
  printf '%s\n\n## Recente repo-wijzigingen (context):\n%s\n' \
    "$(cat "${PROMPT_FILE}")" "${context}" \
    | "${CLAUDE}" -p --permission-mode acceptEdits

  if git diff --quiet -- docusaurus/; then
    echo "agent maakte geen doc-wijzigingen; branch opruimen."
    git checkout -q "${BASE_BRANCH}"
    git branch -q -D "${branch}"
    exit 0
  fi

  git add docusaurus/
  git commit -q -m "docs: auto-update via freshness-agent ($(date +%F))"
  git push -q -u origin "${branch}"
  gh pr create --base "${BASE_BRANCH}" --head "${branch}" \
    --title "docs: auto-update (freshness-agent)" \
    --body "Automatisch voorstel van de docs-freshness-agent (agent-lxc). Review vóór merge. Scrub-policy: geen Tailscale-100.x/secrets."
  echo "PR aangemaakt vanaf ${branch}."
}

main "$@"
