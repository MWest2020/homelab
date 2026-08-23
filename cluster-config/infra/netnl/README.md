# netnl facade

Public batch API v2 facade in front of the VPS Internet.nl batch instance.
Independent instance — not internet.nl, not Platform Internetstandaarden.
Code and design: [MWest2020/internetnl-cli](https://github.com/MWest2020/internetnl-cli)
(`src/netnl/`, `openspec/changes/add-measurement-api/`).

## Topology

```
internet ──443──▶ Tailscale Funnel ──▶ Service netnl:8000 (this cluster)
                                          │  HTTP Basic per tenant
                                          ▼
                              VPS batch instance (tailnet-only)
```

The facade runs here; the batch instance runs on a VPS with a fixed public
IPv4+IPv6 (a NAT'd homelab cannot host the instance) and is reached over the
tailnet. See `docs/how-to/deploy-instance-vps.md` in the internetnl-cli repo.

## Out-of-band Secret (never in Git)

The upstream credential is NOT stored here. Create it once, in the `netnl`
namespace, before/after first sync:

```sh
kubectl -n netnl create secret generic netnl-upstream \
  --from-literal=NETNL_UPSTREAM_USERNAME='<batch-user>' \
  --from-literal=NETNL_UPSTREAM_PASSWORD='<batch-pass>'
```

These are the credentials of a batch user created on the VPS instance with
upstream's `user_manage.sh`. Rotate by recreating the Secret and restarting
the Deployment. (OpenBao-backed injection is the later hardening step, matching
the wordsworth pattern.)

## Before it works

1. Set `NETNL_UPSTREAM_ENDPOINT` in `configmap.yaml` to the instance's tailnet
   address; keep `NETNL_ALLOW_HTTP=1` only if that hop is plain http.
2. Create the `netnl-upstream` Secret (above).
3. Confirm Tailscale Funnel is enabled for the tailnet (ACL `funnel` node
   attribute for the operator tag, HTTPS/MagicDNS on). `funnel.yaml` requests
   the public endpoint; the operator provisions `https://netnl.<tailnet>.ts.net`.
4. Bump the image in `deployment.yaml` / `prune-cronjob.yaml` when a new
   `sha-<short>` is published by the internetnl-cli image workflow. The image
   is pinned by digest (`sha-<short>@sha256:...`); resolve the new digest with
   `docker buildx imagetools inspect ghcr.io/mwest2020/internetnl-cli:sha-<short>`.

## Issue a tenant credential

```sh
kubectl -n netnl exec deploy/netnl -- netnl-admin user add <name>
```

The generated password is printed once. Acceptance check: point the
`internetnl` CLI at `https://netnl.<tailnet>.ts.net` with that credential —
it must work unchanged (only `INTERNETNL_*` differ).

## Retention

`netnl-prune` (CronJob, every 10 min) clears expired requests, stale
`reserving` rows and old audit rows. Cadence bounds the reserving grace.
