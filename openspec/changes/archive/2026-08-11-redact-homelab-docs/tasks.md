# Tasks: redact-homelab-docs

- [x] 1.1 Inventariseer alle concrete identifiers in `docs/` (hostnamen,
      gebruikersnamen, tailnet-namen, LAN-IP's, hardware-identifiers) —
      grep-lijst als werkbasis, niet committen.
- [x] 2.1 Vervang per categorie volgens proposal.md; consistent dezelfde
      placeholder voor dezelfde machine/rol door alle pagina's heen.
- [x] 2.2 Leesbaarheidscheck: elke geredigeerde pagina blijft uitvoerbaar
      als instructie (een lezer met eigen hostnames kan hem volgen).
- [x] 2.3 `last_reviewed` bijwerken op elke gewijzigde pagina.
- [x] 3.1 Zelfcheck: `grep -rniE '<eigen lijst uit 1.1>' docs/` levert nul
      treffers op categorieën 1–5.
- [x] 4.1 Security-gate (Claude, 2026-08-11): `docs/` bevat geen LAN-IP's,
      tailnet-namen, MAC's of persoonlijke user/hostnamen meer — redactie
      compliant op main. Enige rest: publieke DNS (1.1.1.1/8.8.8.8, didactisch)
      en het publieke domein `westerweel.work` — beide behouden per de regel
      "publieke URL's niet vervangen" (domein-redactie apart geflagd bij Mark).
      Thuislab-mandaat: op main, geen PR.
