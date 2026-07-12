# Habitat builder — apply-docs-contract

_run_id builder-apply-docs-contract-20260712-185049 · verdict ok · 2026-07-12T18:57:07Z_

---

Done. Everything is committed on the working branch; **push/PR awaits your explicit confirmation** (CLAUDE.md: `git push` always asks).

## Run report — `apply-docs-contract`

**SECURITY-SCRUB (task 1.2):** Searched the whole repo. **No real secrets found.** Every credential reference is a placeholder (`JOUW_TOKEN`, `changeme-encrypt-this`), an env-var indirection (`${DB_PASSWORD}`), out-of-band secret creation, or a `.example` file. Nothing removed; **nothing already-pushed to report for rotation.** Hostnames/IPs/topology left in place per your 2026-07-12 decision.

**Migration (2.1–2.3):**
- `00/01/02` → `reference/`; `03–07`, `20–26`, `30` → `how-to/`; both `BUILDLOG*` → `explanation/`. Number prefixes kept. Used `git mv` (history preserved).
- Front matter on **every** page: migrated-without-review → `status: draft`, `last_reviewed: 2026-07-12`. No `owner` field.
- Redirect **stubs** left at old paths only where real in-repo external links exist (README, CLAUDE.md, CHANGELOG, k8s READMEs, claude-lxc-iac) → `00,01,02,03,04,07,20,22,23,24,25`. The internal-only docs (`05,06,21,26,30,BUILDLOG*`) got no stub. Stubs carry `status: deprecated`.
- Internal cross-directory links rewritten (e.g. `../reference/02-network.md`). All links resolve **except** the 07-11 links in `06-kubernetes.md`, which were **already dead before** migration (those files never existed in git) — out of scope.
- New `docs/index.md` (entry point → README, sections, and the explicit **"not in the public handbook import — private section"** note per Westmarch change 2 task 3.1).
- New `docs/how-to/gpu-cuda-reset.md`.

**`.mcp.json` (2.4):** Already present from the seed and matches the template (`url: TODO-change-3`) — left unchanged.

**Self-check (3.1):** All content pages live only in `reference/`/`how-to/`/`explanation/`; the root holds only `index.md` plus the contract-authorized redirect stubs. Every page has `status` + `last_reviewed`. One language: Dutch.

**Scope:** Only `docs/` changed. `CLAUDE.md`, `.claude/agents/`, CI, `docusaurus/`, README, and all infra dirs untouched.

**Note on task 1.1:** habitat put me on branch `habitat/builder/apply-docs-contract` (off `main`), not literally `docs/contract`. The intent (isolated working branch, no merge) is satisfied; I worked there rather than fighting the harness.

---

**Proposed PR** — title `docs: apply handbook docs contract`. Ready when you confirm:

Shall I `git push` this branch and open the PR? (I'll stop there — you merge.)
