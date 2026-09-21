# Tasks: cloudflare-afhankelijkheid

## 1. Meten wat we zelf zijn
- [ ] 1.1 `iam.westerweel.work`, `wordsworth.westerweel.work` en
  `api.westerweel.work` op het Wanderer-scanschema, naast
  `westerweel.work` dat er al op staat.
- [ ] 1.2 Eén meting vastleggen als nulpunt: welke van onze eigen namen
  scoren waarop, met datum.

## 2. De zone weg bij Cloudflare
- [ ] 2.1 Een Europese DNS-aanbieder kiezen en de zone `westerweel.work`
  daarheen verhuizen; de CNAME's naar `*.cfargotunnel.com` blijven
  werken zolang de tunnels blijven.
- [ ] 2.2 Nameservers omzetten en nameten dat alle namen blijven
  antwoorden (inclusief de tunnels en de Pages-sites).
- [ ] 2.3 Vastleggen wat er bij Cloudflare achterblijft en waarom.

## 3. De ingang per dienst
- [ ] 3.1 Besluit per naam: blijven, Funnel, of eigen terminatie — met
  de reden erbij.
- [ ] 3.2 Eerste kandidaat uitvoeren: eigen terminatie voor
  `iam.westerweel.work` (VPS bij een Europese aanbieder, WireGuard naar
  het cluster, TLS op die VPS).
- [ ] 3.3 Nameten: inlogstroom werkt, TLS eindigt aantoonbaar bij ons.

## 4. Vastleggen
- [ ] 4.1 Per publieke naam de gekozen route en de reden, in de docs.
- [ ] 4.2 CHANGELOG-regel.
