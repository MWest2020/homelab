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

- **Public:** `https://iam.westerweel.work` through a Cloudflare tunnel whose
  ingress lets only `^/realms/`, `^/resources/` and `^/js/` through.
- **Admin console:** not public (404). Tailnet only, through a **Tailscale
  Ingress** with a MagicDNS certificate. Not a LoadBalancer Service on
  http:8080: a browser tries https first and hangs. Wanderer uses the same
  construction.

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

- **Service selector.** The tunnel's cloudflared pods also carry
  `app: keycloak`. A Service selecting only on that sends two thirds of the
  traffic to the tunnel pods and connections drop. Always select on
  `component: server` as well.
- **A Deployment selector is immutable.** Adding that label requires
  `kubectl delete deploy` and letting Argo CD recreate it.
- **A trailing newline in a secret.** `kubectl create secret --from-file` with
  a file ending in `\n` puts the newline *in* the value. The bootstrap admin
  was unusable through HTTP login because of it. Write password files without
  a newline (`printf '%s'`, or `print(..., end='')`). When in doubt, `kcadm.sh`
  inside the pod uses the env value literally and does work.
