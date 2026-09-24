# Nulpunt: onze eigen namen, gemeten door Wanderer

Vastgelegd 2026-09-24, uit de productie-instantie van Wanderer (v0.11.0).
Perimeterscans van 2026-09-23 10:39 UTC; de standards-dimensie uit de
internet.nl-meting van dezelfde dag (CronJob `wanderer-standards`).

## Soevereiniteit per stroom

| naam | hosting | mail | DNS | certificaat | netwerkpad | hyperscaler | derde partijen | score |
|---|---|---|---|---|---|---|---|---|
| `westerweel.work` | afhankelijk | soeverein | afhankelijk | afhankelijk | onbekend | afhankelijk | onbekend | 1/5 |
| `iam.westerweel.work` | afhankelijk | – | – | afhankelijk | onbekend | afhankelijk | onbekend | 0/3 |
| `wordsworth.westerweel.work` | afhankelijk | – | – | afhankelijk | onbekend | afhankelijk | onbekend | 0/3 |
| `api.westerweel.work` | afhankelijk | – | – | afhankelijk | onbekend | afhankelijk | onbekend | 0/3 |

– = niet gemeten voor een subdomein (geen eigen MX of zone).

De redenen, zoals Wanderer ze geeft:

- **Hosting:** apex-adressen in CA (Cloudflare, Inc.) — voor alle vier.
- **DNS:** nameservers in CA, GB, CR, US (Cloudflare, Inc.).
- **Certificaat:** uitgegeven in de VS — de edge-certificaten van Cloudflare.
- **Hyperscaler:** Cloudflare, Inc.
- **Mail** is het enige soevereine punt: mailservers in NL (Soverin B.V.).

Alle afhankelijke punten hebben één oorzaak. Zolang de zone en de tunnels bij
Cloudflare staan, verandert hier niets; dit is dus het getal om de secties 2
en 3 aan af te meten, als ze ooit uitgevoerd worden.

## Standards (internet.nl)

| naam | DNSSEC | IPv6 | mail-auth | RPKI | STARTTLS/DANE | TLS |
|---|---|---|---|---|---|---|
| `westerweel.work` | soeverein | voldoende | soeverein | soeverein | onbekend | voldoende |
| `iam.westerweel.work` | soeverein | soeverein | – | soeverein | – | voldoende |
| `wordsworth.westerweel.work` | soeverein | soeverein | – | soeverein | – | voldoende |
| `api.westerweel.work` | soeverein | voldoende | – | soeverein | – | voldoende |

Technisch staat het er goed voor. De afhankelijkheid zit in wíe het draait,
niet in hoe.
