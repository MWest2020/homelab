# jarvis

The voice bridge (MWest2020/jarvis), tailnet only: `http://jarvis.<tailnet>.ts.net:8787`.
Runbook: `docusaurus/docs/runbooks/jarvis.md` (shape, secrets, new build, checks).

- Out-of-band secrets in namespace `jarvis`: `claude-oauth-token`, `pat-node-01` and
  `ghcr-pull` copied from `agents`; `jarvis-token` (key `token`) with the phone's token; `jarvis-agent-key` (keys `key`: the bridge's ed25519 private key, `known_hosts`: `192.168.178.58 ssh-ed25519 …` taken from agent-lxc's /etc/ssh/ssh_host_ed25519_key.pub) for full mode. The public half is in agent-lxc's ~/.ssh/authorized_keys as `restrict,from="192.168.178.207",command="/usr/local/lib/jarvis-agent/turn" …`.
- The Argo CD Application (`apps/infrastructure/jarvis.yaml`) is applied once by hand
  (no root app runs; see the runbooks index).
