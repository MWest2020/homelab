# Habitat reviewer — apply-docs-contract

_run_id reviewer-apply-docs-contract-20260712-185756 · verdict ok · 2026-07-12T18:59:35Z_

---

All checks are complete. Read-only review — here is my verdict.

## Reviewer verdict: **PASS**

Change under review: `apply-docs-contract` — diff `main...HEAD` (commits `8928189` docs + `f5fe202` habitat run).

### 1. Scope ✅
The diff implements the change's tasks and nothing beyond it:
- Numbered docs reorganised per the repo-specific mapping: `00/01/02` → `reference/`, `03–07 / 20–26 / 30` → `how-to/`, both BUILDLOGs → `explanation/`.
- New `how-to/gpu-cuda-reset.md` documents the `rmmod nvidia_uvm && modprobe nvidia_uvm` fix with symptoms + when-to-apply, as required.
- `docs/index.md` added; `.mcp.json` present with `url: "TODO-change-3"` placeholder intact (task 2.4).
- Non-content files in the diff (`.habitat/audit.jsonl`, `.habitat/run-*`, `run-report.json`) are habitat harness artifacts from the builder run, not authored content — not a scope violation.

### 2. Contract ✅
- Markdown lives only in `index.md`, `how-to/`, `reference/`, `explanation/` — **plus** deprecated stubs at the old top-level paths. The stubs are explicitly sanctioned by the proposal ("stub met verwijzing achterlaten op de oude plek"), so this reconciles with the contract rather than breaching it.
- Every page carries YAML front matter with `status` + `last_reviewed: 2026-07-12`. Migrated-without-review pages are `status: draft`; stubs are `status: deprecated`. Correct.
- No `owner` field anywhere (`grep` = NONE).
- One language: Dutch throughout ("Kubernetes the Hard Way" is a proper noun, not a language leak).
- `docs/index.md` links to the README (doesn't replace it) and carries the required "**Niet in de publieke handbook-import**" note (Westmarch change 2, task 3.1).

### 3. Cage intact ✅
Diff touches **no** `CLAUDE.md`, `.claude/agents/`, or CI config.

### 4. No secrets ✅
Full-diff secret scan is clean. The only pattern hit — `Password: [sterk wachtwoord - bewaar veilig!]` — is a placeholder instruction carried over verbatim during migration, not a credential. Hashes in `.habitat/audit.jsonl` / `run-report.json` are diff/entry SHAs, not secrets.

### Non-blocking note (for Mark, not a fix)
Task 4.1 (open PR / push) is correctly left unchecked — `git push` awaits your explicit confirmation per the CLAUDE.md guardrail. Nothing for the reviewer to do here.

No changes made (read-only role).
