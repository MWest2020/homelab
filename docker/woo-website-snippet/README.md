# woo-website (OpenWoo PWA) — klant-snippet

Standalone Docker-compose snippet voor de OpenWoo publieke pagina. Voor partijen die al een eigen Nextcloud met OpenCatalogi-app hebben draaien en alleen deze publieke pagina erbij willen.

**In dit pakket zit alleen het PWA-frontend-deel.** Geen Nextcloud, geen database, geen reverse-proxy — die hebben jullie zelf.

## Wat je nodig hebt

- Een werkende Nextcloud met de **OpenCatalogi**-app geactiveerd (`occ app:enable opencatalogi`).
- De Nextcloud-API moet bereikbaar zijn vanaf de Docker-host waar je deze container draait.
- Een Docker-host met `docker` + `docker compose v2`.
- Een eigen reverse-proxy / TLS-laag (Caddy / nginx / Traefik / ingress) om de pagina onder een publieke hostname te zetten.

## Quickstart

```bash
cp env.example .env
$EDITOR .env             # vul minimaal NEXTCLOUD_HOST, NEXTCLOUD_API_URL en WOO_ORGANISATION_NAME in
docker compose up -d
docker compose logs -f woo-website
```

Wacht tot je in de logs ziet:
```
nginx: [notice] start worker processes
```

Dat betekent dat de container loopt en luistert (standaard op host-port `8081`).

Direct testen:
```bash
curl -sI http://localhost:8081
```
Verwacht `HTTP/1.1 200 OK`.

## Publiek bereikbaar maken

Wijs een publieke hostname (bv. `woo.gemeenteXYZ.nl`) naar deze Docker-host. In je reverse-proxy stuur je `https://woo.gemeenteXYZ.nl` door naar `http://<docker-host>:8081`.

Caddy-voorbeeld:
```
woo.gemeenteXYZ.nl {
    reverse_proxy <docker-host-of-internal-ip>:8081
}
```

Nginx-voorbeeld (relevante blocks):
```nginx
server {
    listen 443 ssl;
    server_name woo.gemeenteXYZ.nl;
    # ... ssl_certificate etc.
    location / {
        proxy_pass http://<docker-host-of-internal-ip>:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Configuratie

Zie `.env.example` — alle variabelen staan met uitleg. Verplicht zijn alleen:
- `NEXTCLOUD_HOST` — hostname van jullie Nextcloud
- `NEXTCLOUD_API_URL` — volledige URL naar de OpenCatalogi-API
- `WOO_ORGANISATION_NAME` — voor in de header

Rest is branding-aanpassingen.

## Updates

```bash
docker compose pull
docker compose up -d
```

Image-tag is `latest`; pin op een specifieke tag als jullie predictable upgrades willen.

## Troubleshooting

| Symptoom | Oorzaak | Fix |
|---|---|---|
| Container restart-loop, log toont `[emerg] unknown "upstream_base" variable` | env-vars in verkeerde casing aangeleverd | Beide casings zetten — image leest deels uppercase, deels lowercase |
| `[emerg] host not found in upstream` | container kan `NEXTCLOUD_HOST` niet DNS-resolven | Vanaf de Docker-host `getent hosts $NEXTCLOUD_HOST` testen; eventueel `extra_hosts` toevoegen aan compose |
| Pagina rendert maar zonder data | OpenCatalogi-app niet actief op Nextcloud, of API niet bereikbaar vanaf container | `curl -v <NEXTCLOUD_API_URL>/themas` testen vanuit de Docker-host |
| Custom theme niet zichtbaar | `WOO_THEME_CLASSNAME` niet gezet of theme niet in image gebakken | Check image-versie; vraag bij ConductionNL na voor custom theme-builds |

## Vragen

ConductionNL maakt en onderhoudt het `woo-website-v2`-image. Voor image-specifieke issues / nieuwe features: https://github.com/ConductionNL/woo-website-template-apiv2
