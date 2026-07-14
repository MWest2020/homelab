# Habitat builder — redact-homelab-docs

_run_id builder-redact-homelab-docs-20260714-073555 · verdict ok · 2026-07-14T07:45:11Z_

---

Klaar. De OpenSpec-change **`redact-homelab-docs`** is geïmplementeerd, uitsluitend binnen `docs/`, en gecommit op de branch `habitat/builder/redact-homelab-docs` (commit `f6fb727`). Niet gepusht, niet gemerged — dat is de gate van Mark/orchestrator na reviewer- én security-PASS.

## Wat er gebeurd is

**16 pagina's geredigeerd**, per categorie uit `proposal.md`:

| Categorie | Vervanging | Placeholder |
|---|---|---|
*[regels met originele identifiers verwijderd vóór merge — security-note reviewer 2026-07-14; mapping staat in de private context]*
| `last_reviewed` | bijgewerkt op elke gewijzigde pagina | `2026-07-14` |

**Placeholder-conventie:** backticked in proza/tabellen/headers (rendert betrouwbaar, matcht de bestaande repo-conventie); bare in code-fences/ASCII-diagram (3 plekken) waar backticks letterlijk of verwarrend zouden zijn.

**Bewust behouden** (buiten de 5 categorieën of expliciet op de keep-lijst):
*[regels met originele identifiers verwijderd vóór merge — security-note reviewer 2026-07-14; mapping staat in de private context]*
- Generieke k8s-namen (`cp-01`, `node-01/02`), tenant-namen (`klant-a/b/c`), pod/service-CIDR (`10.200.0.0/16`, `10.32.0.0/24`), poorten, cloud-user `ubuntu`.
- Publieke URL's/domein `westerweel.work` — staat expliciet op de "NIET vervangen"-lijst.

*[regels met originele identifiers verwijderd vóór merge — security-note reviewer 2026-07-14; mapping staat in de private context]*

## Twee oordelen die de reviewer/security expliciet mag wegen

*[regels met originele identifiers verwijderd vóór merge — security-note reviewer 2026-07-14; mapping staat in de private context]*
2. **`westerweel.work`** — een achternaam-domein en dus feitelijk een persoonlijke identifier, maar de `proposal` zet publieke URL's/domein expliciet op de keep-lijst en noemt domein niet in de 5 vervang-categorieën. Ik heb de letter van de scope gevolgd (behouden). Als Mark het domein tóch weg wil, is dat een scope-uitbreiding voor een aparte beslissing.

Taak **4.1 blijft open** (STOP-gate): werk staat op de branch, klaar voor review.
