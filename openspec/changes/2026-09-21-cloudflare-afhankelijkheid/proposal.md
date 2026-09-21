# Change: cloudflare-afhankelijkheid

> Aanleiding Mark 2026-09-21: de demopagina van Wanderer wees zijn eigen
> domein aan — *"Nee — Hosting: hosted at Cloudflare — apex IPs in
> CA,CA,CA,CA (outside EEA)"*. Zijn reactie: *"zet die
> cloudflare-afhankelijkheid ook in een change."*

## Why

De scanner die wij bouwen om afhankelijkheid van Amerikaanse partijen
aan te wijzen, draait zelf volledig achter een Amerikaanse partij. Dat
is niet alleen ongemakkelijk, het is meetbaar:

- **DNS.** `westerweel.work` heeft `jamie.ns.cloudflare.com` en
  `lennox.ns.cloudflare.com` als nameservers. De hele zone — wie welk
  adres krijgt, welke certificaten uitgegeven mogen worden — wordt daar
  beheerd.
- **Apex-adressen.** `westerweel.work` wijst naar `104.21.86.59` en
  `172.67.215.165`: het proxy-netwerk van Cloudflare, met de apex-IP's
  geregistreerd in **CA**.
- **Elke publieke ingang.** Vier `cloudflared`-tunnels
  (`netnl`, `wordsworth`, `wanderer`, `keycloak`) dragen al het publieke
  verkeer naar dit cluster. TLS eindigt bij Cloudflare, niet bij ons:
  zij zien elk verzoek in klare tekst, inclusief de inlogstroom naar
  Keycloak.
- **Ook de identiteitslaag.** `iam.westerweel.work` loopt door diezelfde
  tunnel. Wie daar meekijkt of de route verlegt, zit bij de voordeur van
  alle apps tegelijk.

Dat laatste is de zwaarste, en het is ironisch: we hebben deze week
Cloudflare Access wéggehaald bij wordsworth om identiteit zelf te
hosten, terwijl het verkeer ernaartoe nog steeds over hun edge loopt.

## Wat dit NIET is

Geen oproep om vanavond alles om te gooien. De tunnels lossen een echt
probleem op: geen open poorten, geen publiek IP, werkt achter CGNAT, en
ze zijn uit echte storingen bijgesteld (twee connectors, http2, DNS over
TCP). Wat hier ontbreekt is niet daadkracht maar een **besluit**: dit is
een bewuste afhankelijkheid, of het is er een die we afbouwen — en zolang
dat niet is opgeschreven, is het geen van beide.

## Wat er moet gebeuren

**1. Meten wat we zelf zijn.** Wanderer scant `westerweel.work` al
wekelijks. Zet ook de andere eigen namen op dat schema
(`iam`, `wordsworth`, `api`), zodat onze eigen voetafdruk in dezelfde
rapportage staat als die van anderen. Meten voor mening.

**2. De zone weghalen bij Cloudflare.** DNS is de lichtste stap met de
grootste symbolische en praktische winst: een Europese DNS-aanbieder
(bijvoorbeeld SIDN voor `.nl`-namen, of TransIP/Hetzner voor de rest)
en de zone daarheen. De tunnels blijven dan nog werken via een CNAME.

**3. De ingang heroverwegen, per dienst.** Drie opties, en ze hoeven
niet voor alles hetzelfde te zijn:
   - **Blijven.** Voor de publieke demo en netnl is meekijken door een
     CDN geen ramp — daar staat niets persoonlijks.
   - **Tailscale Funnel.** Haalt Cloudflare weg, maar zet er een ander
     Amerikaans bedrijf voor terug. Alleen winst als je hun edge meer
     vertrouwt, niet als je soevereiniteit wilt.
   - **Eigen terminatie.** Een kleine VPS bij een Europese aanbieder met
     WireGuard naar dit cluster, TLS op die VPS. Dan eindigt TLS bij ons.
     Dit is de enige optie die het probleem echt oplost, en de enige die
     werk en kosten met zich meebrengt.

**4. Kiezen en opschrijven.** Per naam vastleggen welke route hij loopt
en waarom, zodat de volgende die hier kijkt niet hoeft te raden.

## Besluit (Mark, 2026-09-21)

**We blijven voorlopig bij Cloudflare.** *"zolang we geen users hebben,
blijven we even bij cloudflare … op termijn zelf ook soeverein."*

Dat is een besluit, geen uitstel: zonder gebruikers loopt niemand het
risico dat hierboven staat, en de kosten van eigen terminatie (een VPS,
WireGuard, TLS-beheer) wegen dan niet op tegen wat het beschermt.

**Wanneer dit terugkomt** — zodat het geen gewoonte wordt die niemand
meer bekijkt:

- zodra er andere mensen dan Mark inloggen op `iam.westerweel.work`,
  want dan reist er vreemde identiteit over die edge;
- zodra er een dienst op staat die persoonsgegevens draagt (wordsworth
  met echte dossiers in plaats van gepubliceerde Woo-stukken);
- zodra Wanderer aan derden wordt aangeboden — dan is de eigen
  voetafdruk onderdeel van het aanbod.

Wat we nu wél doen: **meten**. Onze eigen namen komen op hetzelfde
scanschema als de doelen die we voor anderen bekijken, zodat de
afhankelijkheid zichtbaar blijft in plaats van te verdwijnen omdat we
hem kennen.

## Voorstel (voor later, als de trigger afgaat)

Doen: **1 en 2** (meten, en de zone verhuizen). Voor **3** de
identiteitslaag als eerste kandidaat voor eigen terminatie — daar loopt
de inlogstroom, en dat is het enige verkeer waar meekijken direct
gevolgen heeft. De rest blijft voorlopig waar hij is, expliciet en
opgeschreven.

## Out of scope

De Cloudflare Pages-sites (`westerweel-work`, `homelab`) en het
Pages-token; die staan los van dit cluster en verdienen hun eigen
afweging.
