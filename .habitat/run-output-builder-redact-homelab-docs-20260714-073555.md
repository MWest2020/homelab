# Habitat builder — redact-homelab-docs

_run_id builder-redact-homelab-docs-20260714-073555 · verdict ok · 2026-07-14T07:45:11Z_

---

Klaar. De OpenSpec-change **`redact-homelab-docs`** is geïmplementeerd, uitsluitend binnen `docs/`, en gecommit op de branch `habitat/builder/redact-homelab-docs` (commit `f6fb727`). Niet gepusht, niet gemerged — dat is de gate van Mark/orchestrator na reviewer- én security-PASS.

## Wat er gebeurd is

**16 pagina's geredigeerd**, per categorie uit `proposal.md`:

| Categorie | Vervanging | Placeholder |
|---|---|---|
| LAN-IP's | `192.168.178.x` → RFC 5737 voorbeeldbereik (laatste octet + didactische struktuur behouden) | `192.0.2.x` |
| Beheer-/jump-VM | `jumpbox` / `jumpy` / `jump` (44+ treffers) | `` `<beheer-vm>` `` |
| Werkstation | `alma`/`Alma` **als hostnaam** | `` `<werkstation>` `` |
| Gebruikersnaam | `gongoeloe` (persoonlijke ansible-/login-user) | `` `<user>` `` |
| `last_reviewed` | bijgewerkt op elke gewijzigde pagina | `2026-07-14` |

**Placeholder-conventie:** backticked in proza/tabellen/headers (rendert betrouwbaar, matcht de bestaande repo-conventie); bare in code-fences/ASCII-diagram (3 plekken) waar backticks letterlijk of verwarrend zouden zijn.

**Bewust behouden** (buiten de 5 categorieën of expliciet op de keep-lijst):
- Productnamen: Proxmox, Tailscale, Cilium, ArgoCD, en **AlmaLinux als distro** (`RHEL/CentOS/Alma`) — context-onderscheiden van de host `alma`.
- Generieke k8s-namen (`cp-01`, `node-01/02`), tenant-namen (`klant-a/b/c`), pod/service-CIDR (`10.200.0.0/16`, `10.32.0.0/24`), poorten, cloud-user `ubuntu`.
- Publieke URL's/domein `westerweel.work` — staat expliciet op de "NIET vervangen"-lijst.

**Zelfcheck (taak 3.1):** nul treffers meer op categorieën 1–5. Geen tailnet-namen (`*.ts.net`), MAC-adressen of serienummers aangetroffen.

## Twee oordelen die de reviewer/security expliciet mag wegen

1. **`admin`** (SSH/OS-account, o.a. `ssh admin@…`) — behouden als generiek role-account; de categorie zegt "login-/SSH-namen **van personen**", en `admin` is niet-persoonlijk (net als `ubuntu`). Alleen de persoonlijke handle `gongoeloe` is geredigeerd.
2. **`westerweel.work`** — een achternaam-domein en dus feitelijk een persoonlijke identifier, maar de `proposal` zet publieke URL's/domein expliciet op de keep-lijst en noemt domein niet in de 5 vervang-categorieën. Ik heb de letter van de scope gevolgd (behouden). Als Mark het domein tóch weg wil, is dat een scope-uitbreiding voor een aparte beslissing.

Taak **4.1 blijft open** (STOP-gate): werk staat op de branch, klaar voor review.
