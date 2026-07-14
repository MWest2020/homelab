# Tasks: redact-homelab-docs

- [ ] 1.1 Inventariseer alle concrete identifiers in `docs/` (hostnamen,
      gebruikersnamen, tailnet-namen, LAN-IP's, hardware-identifiers) —
      grep-lijst als werkbasis, niet committen.
- [ ] 2.1 Vervang per categorie volgens proposal.md; consistent dezelfde
      placeholder voor dezelfde machine/rol door alle pagina's heen.
- [ ] 2.2 Leesbaarheidscheck: elke geredigeerde pagina blijft uitvoerbaar
      als instructie (een lezer met eigen hostnames kan hem volgen).
- [ ] 2.3 `last_reviewed` bijwerken op elke gewijzigde pagina.
- [ ] 3.1 Zelfcheck: `grep -rniE '<eigen lijst uit 1.1>' docs/` levert nul
      treffers op categorieën 1–5.
- [ ] 4.1 STOP: werk blijft op de branch; Mark/orchestrator merget na
      reviewer- én security-PASS.
