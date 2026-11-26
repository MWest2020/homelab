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

**Excluded on purpose:** `billbird.westerweel.work`, switched off by Mark on
2026-11-25. It is in `EXCLUDED_HOSTS` (`secreport/config.py`): never scanned,
never a gap, and a test fails if it ever lands in `SITES`.

Out of scope: tailnet-only services, and anything that isn't Mark's (no
employer or "conduction" orgs, no other Cloudflare customers). The Funnel
ingresses of convergence and netnl had no public DNS answer on 2026-11-25; the
report checks that every week and says when it changes. The list itself is in
`secreport/config.py`.

## What runs

| Part | Source | Note |
|---|---|---|
| Bot traffic, edge | Cloudflare GraphQL `httpRequestsAdaptiveGroups` + `firewallEventsAdaptive`, plus the tunnel inventory | read-only token `~/.config/cloudflare/read.env`; skipped cleanly when missing. Free plan: sampled counts, no `clientAsn` (IP → ASN locally) |
| Bot traffic, origin | Plesk `logs/` over FTPS (IPv4 only, at most one attempt a day, see backoff below); oauth2-proxy, wanderer, netnl, convergence and Keycloak events via `ssh jumpy kubectl logs` | collected every 3 hours into `~/.local/state/security-report/logs/`; each cluster source separately, so one failure doesn't cost the rest |
| Layer 1 (passive) | security headers + five exposure probes, sslyze, ZAP baseline (spider 1 min, links only: form posting and processing off; passive rules; the active scanner never starts), nuclei with filtered templates (below) | one at a time, each in a scope `secreport-<name>-…` with `MemoryMax=1500M MemorySwapMax=0` |
| Layer 2 (active, non-destructive) | `secreport/layer2.py`: admin paths, encoded-path traversal to the Keycloak admin API, master realm reachability, brute-force config, edge rate limit, client registration, open redirects (Keycloak and oauth2-proxy), proxy bypass, header spoofing, CORS, direct API access, X-Forwarded-For trust; as the **test user** (below): IDOR on documents and reveal without a grant; plus the private checks (below) | GET/OPTIONS, plus: at most a handful of password grants for nonexistent `selfscan-*` users, **one unauthenticated `POST /documents/<dummy id>/reveal`** that oauth2-proxy must stop, and as the test user four POSTs that must get 403 and can't write even without a gate (reveal and reveal.pdf with an unknown grant, reveal with an expired grant of someone else, issuing a grant with a malformed document id). Keycloak config is read with kcadm, never written |

### nuclei: which templates

Not "safe tags" alone; three filters, all must pass (`secreport/layer1.py`):

1. **Directories:** `http/` minus `http/vulnerabilities`, `http/cves`, `http/cnvd`
   and `http/iot`, plus `ssl/`. The `ssl/` templates only run where the TLS end
   is ours, so not against `mwest2020.github.io`.
2. **Tags:** include exposure, misconfig, config, ssl, cors, disclosure, keys,
   token, panel, redirect, takeover, headers; exclude intrusive and instrusive
   (a typo real templates carry), dos, fuzz, bruteforce, default-login, oast,
   rce, sqli, xss, lfi, ssrf, injection, cve, vuln, bypass, auth-bypass,
   backdoor, unauth, register, signup, graphql and more (`NUCLEI_EXCLUDE_TAGS`).
3. **The template file:** dropped if it uses POST/PUT/DELETE/PATCH (a field or
   a raw request), is `self-contained` (those request third parties), uses
   interactsh, `unsafe` raw requests, or a code/javascript/headless/flow block.

`tests/test_nuclei_safe.py` runs `nuclei -tl` with exactly the scan's
arguments and fails if any loaded template breaks rule 3 or comes from an
excluded directory, and also fails if the core GET-only checks `git-config` and
`deprecated-tls` are no longer selected (so coverage cannot vanish silently). The
tags `vuln` and `unauth` are not excluded: they mark most read-only exposure
checks, and rules 1 and 3 already keep the scan safe. nuclei counts `ssl/`
templates as protocol `tcp`, so the ssl run (only `ssl/`, only our own TLS ends)
does not exclude `tcp`; the http run does. On 2026-11-26: 3,135 http + 38 ssl
templates; the file check dropped another 88.

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
- the FTPS log pull: **at most one attempt a day** (`PLESK_MIN_HOURS`, counted
  per attempt, not per success), and **after three failures in a row it stops**
  (`PLESK_MAX_FAILURES`) until someone runs `./run.sh plesk-reset`. Failed FTP
  logins can keep a firewall block alive. State: `plesk-attempts.json`.

If the block comes back: it's the server's firewall (CSF/Imunify), not the
site. It lifts by itself after a while; otherwise Yourhosting support can
whitelist the IP. Then `./run.sh plesk-reset`.

**`Errno 101 Network is unreachable`:** agent-lxc has no IPv6 route, and
`bazibo.nl`/`ftp.bazibo.nl` have AAAA records, so an IPv6 attempt fails at once.
Python then falls back to IPv4; if that also fails you only see the IPv6 error.
The collector now connects over IPv4 only and names the address that failed;
the light TLS check may still show 101. A 101 together with a dead
`curl -4 https://bazibo.nl/` means the IPv4 path is blocked (see above), not IPv6.

## Test user (Wordsworth)

Mark, 2026-11-26 (homelab#85): one test user in realm `westerweel`,
username `selfscan`, address `selfscan@selfscan.invalid` (clearly fake, never
mailed, not on either Wordsworth label list), no groups and no app roles
(only Keycloak's built-in default roles). Realm policy makes TOTP mandatory,
so it has one; the tool enrolled it on its first login and keeps the secret.

- Credentials: `~/.config/security-report/selfscan.env` on agent-lxc (mode
  0600, not in git): `SELFSCAN_USER`, `SELFSCAN_EMAIL`, `SELFSCAN_PASSWORD`,
  `SELFSCAN_TOTP_SECRET`.
- `layer2.selfscan_session()` logs in through oauth2-proxy exactly like a
  browser (form login, then a TOTP code), and checks that Wordsworth itself
  recognises the caller before testing anything. TOTP codes are single-use in
  this realm; the helper waits for the next 30-second step if needed.
- The real document id and grant id the checks aim at are read from
  Wordsworth's database in a read-only transaction at run time, never stored.
- Missing file or a failed login: `ww-idor-documents` and the session half of
  `ww-reveal-without-grant` report `skipped` with the reason.
- Never give this user a group, a role, or an address on a label list. To
  start over: delete the user in the admin console (tailnet), create it again
  with the same file (password from the file, `emailVerified`, first and last
  name set), remove the `SELFSCAN_TOTP_SECRET` line, and let the next run
  enrol a new TOTP.

Note: Wanderer accepts any realm user, so this user can log in there too.

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

**How `~/homelab` stays current:** the weekly service starts with
`git -C ~/homelab pull --ff-only` (a dirty or diverged checkout logs an error
and the run uses what is there); the docs agent also pulls it every Monday.
The collector does not pull.

**After PR #86 is merged** (once):

```bash
git -C ~/homelab pull --ff-only
sed -i '/^SECREPORT_DIR=/d' ~/.config/security-report/env
git -C ~/homelab worktree remove ~/.worktrees/hl-secreport
cp ~/homelab/tools/security-report/systemd/*.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now security-report.timer security-report-collect.timer
```

**Stopping:** scanner scopes live outside the service's cgroup, so `KillMode`
can't reach them. Each service ends with
`ExecStopPost=systemctl --user stop 'secreport-*.scope'`, and ZAP stops a
leftover `secreport-zap-*` scope before it starts (otherwise port 8091 collides).

Secrets, never in git:

- `~/.config/security-report/selfscan.env`: the test user (above).

- `~/.config/cloudflare/read.env`: `CLOUDFLARE_READ_TOKEN`, read-only for
  zone `westerweel.work` (Analytics read, plus Tunnel read for the inventory).
- `~/.config/security-report/bao.env`: `BAO_TOKEN`, a periodic OpenBao token
  (768h) with policy `security-report`, which reads only
  `kv/westerweel/bazibo-ftp`. The collector renews it at most once every 20
  hours (`bao-renewed` stamp), independent of the Plesk pull, so a Plesk
  backoff doesn't let it expire. To issue a new one, use
  the root token from `openbao-keys`, the same way as in
  [key-backups](key-backups.md):

  ```bash
  printf 'path "kv/data/westerweel/bazibo-ftp" { capabilities = ["read"] }\n' | $B policy write security-report -
  $B token create -policy=security-report -period=768h -display-name=security-report -field=token
  ```

## Retention

Every collect prunes: cached request lines (`logs/<site>/<day>.log`) after
**35 days**, weekly reports (`<date>.html`, `<date>.json`) after **26 weeks**
(`CACHE_DAYS`, `REPORT_WEEKS` in `secreport/config.py`). Reports and caches are
written with umask 077 (they hold reproduction steps and visitor IPs); the
directory is 0700.

## Run by hand

```bash
cd ~/homelab/tools/security-report
./run.sh collect
./run.sh report                              # everything, ~1.5 h (nuclei is most of it)
./run.sh plesk-reset                         # after a Plesk backoff, once the cause is fixed
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
git), which `layer2.py` loads if present. It refuses to execute the file unless
it is owned by the running user with no group/other bits; a broken or refused
file shows up as one failed check, the public checks still run. The module exports `CHECKS`,
`SEVERITY`, `WHERE` and `questions(l2)`. Once the fix has landed and a re-test
shows it closed, move the check into `layer2.py` as a regression test and drop
it from the private file.

## Checks

```bash
systemctl --user list-timers 'security-report*'
cat ~/.local/state/security-report/collect-last.json     # per source: lines added, or the error
ls ~/.local/state/security-report/logs/*/ | tail
```

A collect that says `error (n/3)` for `bazibo-nl` is usually the server firewall
(see Errno 101 above), the OpenBao token (`bao` in the same file says whether
the renewal worked), or Plesk FTPS; `stopped after 3 failures` means it waits for
`plesk-reset`. Errors under `k8s` are per source; all five failing means jumpy
wasn't reachable.
