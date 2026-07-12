# Habitat security — apply-docs-contract

_run_id security-apply-docs-contract-20260712-185828 · verdict ok · 2026-07-12T18:59:51Z_

---

Security scan complete. My role is read-only — verdict only — so I make no file changes. Here is my finding.

---

## Security verdict: **PASS**

Change `apply-docs-contract` — scanned diff `main...HEAD` (36 files, +1672/−1280) plus root `.mcp.json`.

### Check 1 — No secrets ✅
Every credential-shaped match in the added lines is safe:
- **Placeholders:** `JOUW_TOKEN`, `Password: [sterk wachtwoord - bewaar veilig!]`, `--from-literal=tsig-key=...`
- **Env indirection:** `${DB_PASSWORD}`, `TF_VAR_proxmox_api_token` (from `.env`)
- **Out-of-band creation / refs:** `kubectl create secret generic …`, `tsigSecretSecretRef`, `apiTokenSecretRef`
- `terraform@pve!terraform` is a Proxmox token **ID/name**, not the secret value — safe.
- The two 64-char hex strings (`ed6fcc…`, `84708d…`) are habitat audit-chain **SHA-256 hashes** (`diff_hash`/`entry_hash`), not credentials.
- No private keys / `-----BEGIN` blocks, no kubeconfig or `client-certificate-data`/`client-key-data`, no credential-bearing URLs (`user:pass@`).

This independently confirms the builder's SECURITY-SCRUB claim in task 1.2: **no real secrets, nothing already-pushed requiring rotation.**

### Check 2 — No unintended sensitive exposure in public-rendered docs ✅
`docs/index.md:14-16` explicitly marks the docs as private-section, **excluded from public handbook import**. Hostnames/IPs/topology (`192.168.178.x`, `cp-01`, `westerweel.work`) are retained — permitted under Mark's explicit 2026-07-12 policy (per proposal).

### Check 3 — `.mcp.json` ✅
Root `.mcp.json` holds only placeholder URL `TODO-change-3`, no tokens or credentialed URLs. (Present from the seed; not modified by this change.)

**No action required from the security role. Nothing to report in the PR body for rotation.**
