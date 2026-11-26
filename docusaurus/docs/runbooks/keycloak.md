---
title: Keycloak
sidebar_position: 3
---

# Keycloak

Keycloak is the identity provider (realm `westerweel`), Argo CD app `keycloak`
(sync-wave 5), manifests in `cluster-config/infra/keycloak/`. The database is
the shared CNPG cluster: role `keycloak` under `managed.roles`, database as a
declarative `Database` CR.

## Access

- **Public:** `https://iam.westerweel.work` through the Cloudflare tunnel
  `keycloak`, then the filtering proxy **keycloak-edge**, then Keycloak. Only
  what an OIDC login in realm `westerweel` needs gets through; everything else
  is a 404 from the proxy (see *Edge proxy* below).
- **Admin console and master realm:** tailnet only,
  `https://keycloak.<tailnet>.ts.net/admin`, through a **Tailscale Ingress**
  with a MagicDNS certificate that goes straight to Keycloak (Service
  `keycloak-server`). Not a LoadBalancer Service on http:8080: a browser tries
  https first and hangs. Wanderer uses the same construction.

## Edge proxy (keycloak-edge)

Since 2026-11-26 (homelab#84). The tunnel's path rules in the Cloudflare
dashboard (`^/realms/`, `^/resources/`, `^/js/`) are **not** a boundary:
Cloudflare, cloudflared and Keycloak each read an encoded path differently,
and the admin API was reachable through them. The rules are still there,
but the boundary is now an nginx in the cluster, in git:
`edge-proxy.yaml` (Deployment, Services, NetworkPolicy) and `edge-proxy.conf`
(the rules).

**Wiring, without a dashboard change.** The tunnel's origin (remote config)
is `http://keycloak.keycloak.svc.cluster.local:8080`. The Service `keycloak`
selects the proxy pods (`component: edge`); Keycloak itself is behind
`keycloak-server`. The NetworkPolicy `keycloak-server-ingress` admits only the
proxy, the Tailscale proxy of `keycloak-ts` and the realm-sync Job, so even a
changed tunnel origin can't skip the proxy. In-cluster callers of
`keycloak:8080` (Wordsworth's JWKS fetch) go through the proxy too.

**What the proxy lets through**, both checks must pass:

1. The raw path (as sent) is canonical: no dot segments, no empty segments,
   no `;` or `\`, and percent-encoding only for bytes that can't change the
   path's structure. Encoded dots, slashes, backslashes, semicolons, `%25`
   (double encoding), control bytes and non-ASCII bytes are refused, as are
   malformed escapes.
2. The normalised path (decoded once, dot segments resolved) is on the
   allow-list:
   - realm `westerweel` only: its discovery document; the OIDC endpoints
     `auth`, `token`, `certs`, `userinfo`, `logout` (plus the logout
     confirmation, the login-status iframe and the third-party-cookie check);
     the login pages (`login-actions/*`); and the account console
     (`account/...`), which is the user's own self-service;
   - theme resources for `login`, `account` and `common` under `/resources/`
     (not the admin theme), and `/js/`.

Everything else gets 404: `/`, `/admin`, the admin REST API, every other
realm including `master`, and inside `westerweel` the endpoints nobody uses
publicly (client registration, introspection, device flow, CIBA, PAR,
brokering, SAML). The request goes to Keycloak unchanged, so what the proxy
approved is what Keycloak routes. Requests nginx itself rejects as malformed
also come back as 404.

The proxy also sets `X-Forwarded-For` from `Cf-Connecting-Ip` (set by
Cloudflare, not by the client), so the IP in Keycloak events can no longer be
chosen by the client.

**Another realm or endpoint in real use?** Add it to the `$kc_path_ok` map in
`edge-proxy.conf` (anchored, case-sensitive) and say in the PR which client
needs it. The config has a hash-suffixed ConfigMap, so the pods roll on merge.

**Checks** (outside, after a change):

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://iam.westerweel.work/admin/            # 404
curl -s -o /dev/null -w '%{http_code}\n' https://iam.westerweel.work/realms/master/.well-known/openid-configuration   # 404
curl -s -o /dev/null -w '%{http_code}\n' https://iam.westerweel.work/realms/westerweel/.well-known/openid-configuration  # 200
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://wordsworth.westerweel.work/   # 302 to oauth2 → Keycloak login
```

The weekly security report (`tools/security-report`, layer 2) repeats this
with the encoded-path variants (`kc-tunnel-path-filter`,
`kc-master-realm-public`).

## Realm in git

`realm-westerweel.json` is applied twice: `--import-realm` creates the realm
if it does not exist, and the PostSync `keycloak-realm-sync` Job overwrites
clients on every sync (see the comments in both manifests). Users are
deliberately not in the file. Client-secret placeholders must be `${VAR}`;
`$(env:VAR)` stays literal.

Secrets are out of band, never in git: `keycloak-db` (in `cnpg-database` and
`keycloak`), `keycloak-admin`, `keycloak-tunnel`, and one per client
(`wanderer-oidc` in `wanderer`, mounted as a file).

## Gotchas

- **Service selector.** The tunnel's cloudflared pods (and the edge proxy)
  also carry `app: keycloak`. A Service selecting only on that sends traffic
  to the wrong pods and connections drop. Always select on `component` as
  well: `edge` for `keycloak`, `server` for `keycloak-server`.
- **Admin through `keycloak:8080` fails.** That name is the edge proxy now
  and answers 404 for `/admin` and `master`. In-cluster admin tooling
  (`kcadm.sh` in the realm-sync Job) uses `http://keycloak-server:8080`, and
  a new pod that needs it must carry a label the NetworkPolicy admits.
- **A Deployment selector is immutable.** Adding that label requires
  `kubectl delete deploy` and letting Argo CD recreate it.
- **A trailing newline in a secret.** `kubectl create secret --from-file` with
  a file ending in `\n` puts the newline *in* the value. The bootstrap admin
  was unusable through HTTP login because of it. Write password files without
  a newline (`printf '%s'`, or `print(..., end='')`). When in doubt, `kcadm.sh`
  inside the pod uses the env value literally and does work.
- **Access tokens live five minutes.** An oauth2-proxy that passes the token
  on (`--pass-authorization-header`, as `wordsworth-auth` does) hands the app
  an expired token five minutes after login unless it refreshes. Set
  `--cookie-refresh` well inside that lifespan; Wordsworth uses `4m`
  (2026-10-24: without it every session fell back to the API-key login page).
