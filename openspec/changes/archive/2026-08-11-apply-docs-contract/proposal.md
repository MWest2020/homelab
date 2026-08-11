# Change: apply-docs-contract

> Seed-change, aangeleverd vanuit Westmarch (personal-handbook, change 2
> add-docs-contract). Uitvoering door een habitat-builder-Job; merge door Mark.

## Why

homelab is de draaiende infra van de hub-and-spoke. Besluit Mark 2026-07-12: repo blijft publiek met als harde eis dat er nooit geheimen in staan; hostnames/topologie mogen blijven. Docs gaan naar de private handbook-sectie.
Zonder uniform contract is handbook-aggregatie zinloos: het handbook (hub)
importeert `docs/` van dit repo at build time.

## What changes

- `docs/` volgens het contract hieronder (additief + migratie van bestaande
  docs; geen verwijderingen buiten wat hieronder expliciet staat).
- `.mcp.json` in de root volgens template (handbook-URL blijft placeholder
  `TODO-change-3`).
- Géén andere wijzigingen. Eén branch, één PR, titel:
  `docs: apply handbook docs contract`.

## Docs-contract (bindend, uit Westmarch add-docs-contract)

```
docs/
  index.md          # wat is dit, status, max 3 regels boilerplate
  how-to/           # taakgericht
  reference/        # feiten (config, API, schema's)
  explanation/      # waarom-besluiten; ADR's onder explanation/adr/NNNN-titel.md
```

- Lege mappen weglaten. Minimum viable: `index.md` + één reference-pagina.
- Front matter per pagina (YAML): `status: current|draft|deprecated` +
  `last_reviewed: <ISO-datum>`. GEEN `owner`-veld.
- Gemigreerde pagina's zonder inhoudelijke review: `status: draft`,
  `last_reviewed` = migratiedatum. Alleen een echte review zet `current`.
- Eén taal per repo (deze repo: Nederlands).
- README blijft; `docs/index.md` verwijst ernaar, vervangt niet.
- Bestaande losse docs migreren; stub met verwijzing achterlaten op de oude
  plek als er externe links naartoe kunnen bestaan.


## Repo-specifiek

- SECURITY-SCRUB (eerst, vóór herstructurering): doorzoek de hele repo op
  echte geheimen — tokens, wachtwoorden, private keys, credential-URLs,
  kubeconfig-inhoud, niet-versleutelde vault-bestanden. Verwijder of vervang
  door env-/SOPS-verwijzing. Hostnames, IP's en topologie zijn per besluit
  van Mark acceptabel en blijven staan. Gevonden geheimen die al gepusht
  zijn: vermeld ze expliciet in de PR-body (rotatie is aan Mark).
- Herindeling van de genummerde docs (00–30):
  `00-overview`, `01-hardware`, `02-network` → `reference/`;
  `03-installation` t/m `07-vm-provisioning-stack`, `20-stappenplan-gitops`
  t/m `26-argocd-bootstrap`, `30-migratie-kubeadm` → `how-to/`;
  BUILDLOG's → `explanation/`. Nummerprefixen mogen blijven in bestandsnamen.
- Nieuw `how-to/gpu-cuda-reset.md`: de terugkerende CUDA UVM-reset-fix
  (`rmmod nvidia_uvm && modprobe nvidia_uvm`), wanneer toe te passen.
- `docs/index.md`: vermeld expliciet dat deze docs NIET in de publieke
  handbook-import gaan (private sectie), conform Westmarch change 2 taak 3.1.
- docusaurus/-map staat los van dit contract: NIET aanraken.
- Taal: Nederlands.

## Non-goals

- Geen merge (Mark merget), geen scope buiten deze change, geen wijzigingen
  aan CLAUDE.md / .claude/agents/ / CI.
