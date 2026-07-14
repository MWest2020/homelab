# Change: redact-homelab-docs

> Seed vanuit handbook. Besluit Mark 2026-07-14: de homelab-docs gaan in de
> PUBLIEKE handbook-import, mits geredigeerd — geen letterlijke
> identifiers. Uitvoering door habitat-builder; security-rol is de gate.

## Why

De homelab-documentatie (herstelvolgorde, how-to's, referentie) is publiek
waardevol en bevat geen geheimen meer (scrub 2026-07-12), maar wél concrete
identifiers. Na redactie kan de sectie de publieke site op en vervalt de
afhankelijkheid van de private build voor homelab.

## What changes

UITSLUITEND bestanden onder `docs/`. Ansible/Terraform/scripts en alle
overige mappen blijven onaangeroerd (daar mogen concrete namen blijven).

Vervang in elke pagina onder `docs/`:

1. **Machinenamen/hostnamen** → generieke rolnamen tussen punthaken of de
   bestaande generieke clusternamen. Voorbeelden van het patroon (leid de
   concrete namen af uit de docs zelf, ze staan erin):
   - de GPU-/werkstation-node → `<gpu-node>` of `<werkstation>`
   - de mini-pc-nodes → hun generieke clusternamen (cp-01/node-01-stijl is
     al generiek en mag blijven)
   - de beheer-/jump-VM → `<beheer-vm>`
2. **Gebruikersnamen** (login-/SSH-namen van personen) → `<user>`.
3. **Tailnet-machinenamen en tailnet-domein** (`*.ts.net`) → `<tailnet-naam>`.
4. **LAN-IP-adressen** (192.168.x.x e.d.) → `<node-ip>` / `<lan-subnet>` waar
   het IP zelf niet didactisch nodig is; in configuratievoorbeelden mag een
   gedocumenteerd voorbeeldbereik (RFC 5737 / 192.0.2.x) gebruikt worden.
5. **Serienummers, MAC-adressen en andere unieke hardware-identifiers** →
   weglaten of `<...>`-placeholder.

NIET vervangen: productnamen en technologieën (Proxmox, Tailscale, Cilium,
ArgoCD enz.), generieke k8s-namen (cp-01, node-01), poortnummers, en
publieke URL's. De tekst moet leesbaar en instructief blijven — redactie,
geen lobotomie.

Werk `last_reviewed` bij op elke gewijzigde pagina; zet `status: current`
alleen als de pagina inhoudelijk klopt na redactie, anders laten staan.

## Non-goals

- Geen herstructurering (structuur is al contract-conform).
- Geen wijzigingen buiten `docs/`.
- Geen merge; PR-titel: `docs: redact identifiers for public handbook import`.
