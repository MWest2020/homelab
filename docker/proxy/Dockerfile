# Custom Caddy build met de CrowdSec L7-bouncer (fase A.2).
# Vervangt de stock caddy:2-alpine: die mist de bouncer-module.
#
# Gepind (geen floating tags — boring & auditable):
#   - Caddy 2.11.4            (matcht de versie die op de proxy draaide)
#   - bouncer http-handler    github.com/hslatman/caddy-crowdsec-bouncer/http@v0.13.1
#
# Lokaal gebouwd door deploy-proxy.yml (docker compose build).
ARG CADDY_VERSION=2.11.4

FROM caddy:${CADDY_VERSION}-builder AS builder
RUN xcaddy build \
    --with github.com/hslatman/caddy-crowdsec-bouncer/http@v0.13.1

FROM caddy:${CADDY_VERSION}-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
