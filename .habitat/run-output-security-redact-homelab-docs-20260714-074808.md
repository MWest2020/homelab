# Habitat security — redact-homelab-docs

_run_id security-redact-homelab-docs-20260714-074808 · verdict ok · 2026-07-14T07:50:32Z_

---

I have everything I need for a verdict. Let me summarize my findings.

## Security verdict: **PASS** (with one non-blocking note)

**Scope reviewed:** the full diff of branch `habitat/security/redact-homelab-docs` vs `main` — 17 files under `docs/` plus the habitat tooling artifacts (`.habitat/*`, `run-report.json`, `openspec/.../tasks.md`).

### Check 1 — No secrets ✅
No secret *values* are introduced anywhere in the diff. Every token/credential reference in `docs/` is a placeholder or procedural instruction that predates this change (`JOUW_TOKEN`, `<token>`, `--from-literal=api-token=...`, `kubeadm join ... --token ...`). The redaction only swaps identifiers; it adds no keys, passwords, kubeconfigs, or credential-bearing URLs. `.mcp.json` is not in the diff.

### Check 2 — No unintended sensitive exposure in public docs ✅
The `docs/` redaction is complete and consistent per the owner's explicit policy in the proposal:
- **Zero** residual real LAN IPs (`192.168.x`) — all → RFC 5737 `192.0.2.x`.
- **Zero** `gongoeloe` / `jumpy` / `jumpbox` / `alma`-workstation references — → `<user>`, `<beheer-vm>`, `<werkstation>`. The two remaining "Alma" hits are **AlmaLinux** the distro (correct to keep — a product name).
- No `*.ts.net` / tailnet names, MAC addresses, or serial numbers present.
- `admin` / `ubuntu` retained as generic non-personal accounts — reasonable and matches the proposal's "login names *of persons*" wording.
- `*.westerweel.work` retained — public URL, explicitly out of scope per proposal.
- `last_reviewed` bumped to `2026-07-14` on every touched page.

### ⚠️ Non-blocking note (for the orchestrator / import step)
The committed builder report `.habitat/run-output-builder-redact-homelab-docs-20260714-073555.md` (lines 15–32) re-embeds the **original un-redacted identifiers in cleartext** as a mapping table — `192.168.178.x`, `jumpbox`/`jumpy`, `gongoeloe`. This file is a build-tooling audit artifact, not part of the `docs/` content the proposal scopes for public rendering, and these identifiers are not secrets — so it does **not** block PASS. But if `.habitat/` were ever swept into the public handbook import, the redaction would leak. Recommend the import be scoped to `docs/` only (as the proposal already states), and/or that this artifact not be published.

Per task 4.1, work stays on the branch — I've made no edits, commits, or pushes (read-only role). This is the security gate's **PASS**; merge remains with Mark/orchestrator after the reviewer PASS.
