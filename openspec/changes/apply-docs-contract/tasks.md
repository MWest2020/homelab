# Tasks: apply-docs-contract

- [x] 1.1 Branch `docs/contract` vanaf de default branch. (Uitgevoerd op de door
      habitat aangemaakte werkbranch `habitat/builder/apply-docs-contract`, afgeleid
      van `main`; niet gemerged.)
- [x] 1.2 SECURITY-SCRUB volgens proposal.md (geheimen eruit; hostnames blijven).
      Hele repo doorzocht: geen echte geheimen gevonden. Alle credential-referenties
      zijn placeholders (`JOUW_TOKEN`, `changeme-encrypt-this`), env-var-indirecties
      (`${DB_PASSWORD}`), out-of-band secret-creatie of `.example`-bestanden. Niets
      verwijderd; niets reeds-gepusht om te roteren.
- [x] 2.1 `docs/`-structuur aanleggen volgens het contract; bestaande docs
      migreren zoals beschreven in proposal.md (repo-specifiek); stubs
      achterlaten waar externe links kunnen bestaan.
- [x] 2.2 Front matter op elke pagina: gemigreerd-zonder-review =
      `status: draft` + `last_reviewed` = migratiedatum.
- [x] 2.3 `docs/index.md`: één alinea wat het project is, status, link naar
      README, links naar de aanwezige secties.
- [x] 2.4 `.mcp.json` in de root plaatsen (template uit de seed; placeholder `TODO-change-3` laten staan).
      Reeds aanwezig vanuit de seed en conform template; ongewijzigd gelaten.
- [x] 3.1 Zelfcheck tegen het contract: alleen toegestane submappen dragen
      markdown, elke pagina heeft front matter, één taal (Nederlands).
- [ ] 4.1 PR openen met titel `docs: apply handbook docs contract`; body vinkt
      per contractpunt af wat is toegepast + vermeldt de punten die de
      proposal als "PR-body" markeert. STOP daarna: Mark merget.
      (Lokaal gecommit; `git push`/PR wacht op expliciete bevestiging van Mark
      conform CLAUDE.md-guardrail.)
