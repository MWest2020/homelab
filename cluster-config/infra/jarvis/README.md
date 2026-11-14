# jarvis

The voice bridge (MWest2020/jarvis), tailnet only: `http://jarvis.<tailnet>.ts.net:8787`.
Runbook: `docusaurus/docs/runbooks/jarvis.md` (shape, secrets, new build, checks).

- Out-of-band secrets in namespace `jarvis`: `claude-oauth-token`, `pat-node-01` and
  `ghcr-pull` copied from `agents`; `jarvis-token` (key `token`) with the phone's token.
- The Argo CD Application (`apps/infrastructure/jarvis.yaml`) is applied once by hand
  (no root app runs; see the runbooks index).
