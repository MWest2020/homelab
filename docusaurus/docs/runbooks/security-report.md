---
title: Weekly security report
sidebar_position: 14
---

# Weekly security report

Once a week a report on Mark's own public surface: what bot traffic tries to
reach it, plus a self-scan. Mark, 2026-11-25: one report a week, active testing
(layer 2) allowed, since everything he runs himself is test/development. The
tool is `tools/security-report/` in this repo. It runs on **agent-lxc** as two
systemd user timers. The output is a Dutch HTML page (facts, then gaps with
where they were found, then numbered questions) plus a JSON file, in
`~/.local/state/security-report/<date>.{html,json}`. The coding session mails
the HTML to Mark; the tool never sends mail.

## Scope

| What | Hostnames |
|---|---|
| Cloudflare tunnels (cluster) | `iam`, `wordsworth`, `wanderer`, `api`, `convergence` `.westerweel.work` |
| Cloudflare Pages | `westerweel.work`, `www.westerweel.work` |
| Yourhosting Plesk | `bazibo.nl`: the site only, never the panel or the mail server; light checks only (below) |
| GitHub Pages | `mwest2020.github.io/bazibo` (headers, ZAP, nuclei; the TLS is GitHub's) |

The Cloudflare tunnel inventory in the report lists every public hostname on
the account, so a hostname published outside these tunnels shows up as a gap.

Out of scope: tailnet-only services, and anything that isn't Mark's (no
employer or "conduction" orgs, no other Cloudflare customers). The Funnel
ingresses of convergence and netnl had no public DNS answer on 2026-11-25; the
report checks that every week and says when it changes. The list itself is in
`secreport/config.py`.

## What runs

| Part | Source | Note |
|---|---|---|
| Bot traffic, edge | Cloudflare GraphQL `httpRequestsAdaptiveGroups` + `firewallEventsAdaptive`, plus the tunnel inventory | read-only token `~/.config/cloudflare/read.env`; skipped cleanly when missing. Free plan: sampled counts, no `clientAsn` (IP → ASN locally) |
| Bot traffic, origin | Plesk `logs/` over FTPS; oauth2-proxy, wanderer, netnl, convergence and Keycloak events via `ssh jumpy kubectl logs` | collected every 3 hours into `~/.local/state/security-report/logs/` |
| Layer 1 (passive) | security headers, sslyze, ZAP baseline (spider 1 min + passive rules), nuclei with safe tags only | one at a time, each in `systemd-run --user --scope -p MemoryMax=1500M -p MemorySwapMax=0` |
| Layer 2 (active, non-destructive) | `secreport/layer2.py`: admin paths, brute-force config, edge rate limit, client registration, open redirects (Keycloak and oauth2-proxy), proxy bypass, header spoofing, CORS, direct API access; plus the private checks (below) | GET/OPTIONS only, plus at most a handful of password grants for nonexistent `selfscan-*` users; Keycloak config is read with kcadm, never written |

Our own requests carry the user-agent `westerweel-selfscan/1.0 (…)`; logs
without a user-agent leave out the scan's time window
(`selfscan-windows.json`).

### Shared hosting: go easy

`bazibo.nl` sits on a shared Plesk server with a flood-sensitive firewall. On
2026-11-25 a full sslyze run (cipher enumeration: hundreds of handshakes in a
few seconds) got Mark's home IP blocked on the whole server (site, panel, FTP;
`ping 92.63.174.175` no longer answered from agent-lxc or jumpy). Since then
`bazibo.nl` gets:

- a light TLS check: one handshake per protocol version, a second apart, plus
  the certificate;
- no nuclei and no ZAP spider; the five exposure probes (`/.git/config`, `/.env`, …)
  at one request per second, like every other site;
- the FTPS log pull at most once a day (`PLESK_MIN_HOURS`).

If the block comes back: it's the server's firewall (CSF/Imunify), not the
site. It lifts by itself after a while; otherwise Yourhosting support can
whitelist the IP.

## Install (agent-lxc)

```bash
cd ~/homelab/tools/security-report
./install-scanners.sh                     # nuclei, nuclei-templates, ZAP: pinned + sha256-checked
uv sync --frozen                          # Python deps from uv.lock
mkdir -p ~/.config/systemd/user
cp systemd/security-report{,-collect}.{service,timer} ~/.config/systemd/user/   # copies, not links: survive a removed worktree
systemctl --user daemon-reload
systemctl --user enable --now security-report.timer security-report-collect.timer
```

The units run `$SECREPORT_DIR/run.sh` when `~/.config/security-report/env` sets
`SECREPORT_DIR` and that checkout exists (used while the tool lived in a
worktree), and `~/homelab/tools/security-report` otherwise.

Secrets, never in git:

- `~/.config/cloudflare/read.env`: `CLOUDFLARE_READ_TOKEN`, read-only for
  zone `westerweel.work` (Analytics read, plus Tunnel read for the inventory).
- `~/.config/security-report/bao.env`: `BAO_TOKEN`, a periodic OpenBao token
  (768h) with policy `security-report`, which reads only
  `kv/westerweel/bazibo-ftp`. Every collect renews it. To issue a new one, use
  the root token from `openbao-keys`, the same way as in
  [key-backups](key-backups.md):

  ```bash
  printf 'path "kv/data/westerweel/bazibo-ftp" { capabilities = ["read"] }\n' | $B policy write security-report -
  $B token create -policy=security-report -period=768h -display-name=security-report -field=token
  ```

## Run by hand

```bash
cd ~/homelab/tools/security-report
./run.sh collect
./run.sh report                              # everything, ~1 h (nuclei is most of it)
./run.sh report --skip zap,nuclei            # quick: logs, Cloudflare, headers, TLS, layer 2
systemctl --user start security-report.service   # as the timer would
journalctl --user -u security-report -n 50
ls -l ~/.local/state/security-report/latest.html
```

## A new finding

Only `broken` layer-2 checks and scanner hits of medium or higher count as
findings. Each real one becomes an issue in the repo it belongs to, labelled
`security`. **Never put a working exploit for something unfixed in a public
issue**: describe the class and the fix, and keep the steps in the private
report. Put the issue URL in `known-issues.json` (check id → URL) so the next
report links it.

## Private checks for open findings

A check whose requests are a working exploit for something still unfixed does
not go into this public repo. It lives in
`~/.config/security-report/private_checks.py` on agent-lxc (mode 0600, not in
git), which `layer2.py` loads if present. The module exports `CHECKS`,
`SEVERITY`, `WHERE` and `questions(l2)`. Once the fix has landed and a re-test
shows it closed, move the check into `layer2.py` as a regression test and drop
it from the private file.

## Checks

```bash
systemctl --user list-timers 'security-report*'
cat ~/.local/state/security-report/collect-last.json     # per source: lines added, or the error
ls ~/.local/state/security-report/logs/*/ | tail
```

A collect that says `error` for `bazibo-nl` is usually the OpenBao token (expired?
`bao token lookup`) or Plesk FTPS. One that says `error` for `k8s` means jumpy
wasn't reachable.
