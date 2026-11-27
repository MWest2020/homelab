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

### BMC bridge and Bazibo keys: Secret `netnl-bridge`

The BMC webhook bridge (`NETNL_BMC_WEBHOOK_SECRET`, `NETNL_PUBLIC_ENDPOINT`,
`NETNL_SMTP_*`, `NETNL_SUPPORTER_NOTIFY`) and the Bazibo unlock-code keys
live in the out-of-band Secret `netnl-bridge` (mounted `optional: true`):

- `NETNL_BAZIBO_SIGNING_KEY`: base64 raw 32-byte Ed25519 seed. Operator
  copy: `~/.config/bazibo-unlock/ed25519.key` on agent-lxc (0600). Never
  rotate casually: every sold code is verified in Bazibo against its
  public key (`NETNL_BAZIBO_PUBLIC_KEY` in `configmap.yaml`).
- `NETNL_BAZIBO_DEVICE_SALT`: server secret for the device hashes
  (`openssl rand -hex 32`). Losing it only means devices are counted
  afresh.

Add or change a key without printing it (from a host with the value in a
file; the patch travels on stdin):

```sh
python3 -c 'import base64,json,sys; print(json.dumps({"data":{sys.argv[1]: base64.b64encode(open(sys.argv[2]).read().strip().encode()).decode()}}))' \
  NETNL_BAZIBO_SIGNING_KEY ~/.config/bazibo-unlock/ed25519.key \
  | ssh jumpy 'kubectl -n netnl patch secret netnl-bridge --type merge --patch-file /dev/stdin'
kubectl -n netnl rollout restart deploy/netnl
```

Bazibo is dormant until `NETNL_BAZIBO_EXTRA_ID` is set in `configmap.yaml`
(see the comment there).

## Before it works

1. Set `NETNL_UPSTREAM_ENDPOINT` in `configmap.yaml` to the instance's tailnet
   address; keep `NETNL_ALLOW_HTTP=1` only if that hop is plain http.
2. Create the `netnl-upstream` Secret (above).
3. Confirm Tailscale Funnel is enabled for the tailnet (ACL `funnel` node
   attribute for the operator tag, HTTPS/MagicDNS on). `funnel.yaml` requests
   the public endpoint; the operator provisions `https://netnl.<tailnet>.ts.net`.
4. Bump the image in `deployment.yaml`, `prune-cronjob.yaml`, `measure-cronjob.yaml`
   and `bazibo-watch-cronjob.yaml` when a new
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

## Bazibo watch

`netnl-bazibo-watch` (CronJob, every 5 min) runs `netnl-admin bazibo watch`:
one mail to `NETNL_BAZIBO_ALERT_TO` (mark@westerweel.work) per transaction
that qualified for a Bazibo code and has none delivered after 15 minutes
("Bazibo-code niet verstuurd voor transactie <txn> — controleer"). Fix with
the hand issue in the mail; it never sends a second code for the same
transaction. See internetnl-cli `docs/how-to/supporter-webhook.md`.
