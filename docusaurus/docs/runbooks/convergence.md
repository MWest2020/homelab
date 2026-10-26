---
title: Convergence
sidebar_position: 7
---

# Convergence

The game's site, 2D demo and server-authoritative game server
(MWest2020/convergence), **devnet only**. Argo CD app `convergence`
(sync-wave 7, after the tailscale-operator), manifests in
`cluster-config/infra/convergence/`.

## Shape

One pod, two containers, both pinned by digest:

- `server`: the game server, WebSocket `/ws` on `127.0.0.1:8787`. The game
  state lives in the process, so one replica and `Recreate`.
- `web`: nginx on `:8080`; the site at `/`, the demo at `/play/`, and `/ws`
  and `/healthz` proxied to the server. Site, demo and WebSocket share one
  origin.

Both containers run non-root with a read-only root filesystem and all
capabilities dropped; nginx gets an `emptyDir` on `/tmp` for its pid file.

## Access

- **Public:** `https://convergence.westerweel.work` through the Cloudflare
  tunnel `convergence` (remotely managed; ingress rule and CNAME created by API
  on 2026-10-25). The cloudflared pods carry their own label
  (`app: convergence-tunnel`): the game Service selects `app: convergence`.
- **Funnel:** `https://convergence.<tailnet>.ts.net` is configured but **not
  public**: the tailnet ACL does not grant `tag:k8s` the `funnel` node
  attribute, so the name has no public DNS (netnl's Funnel has the same gap).
  Fix, tailnet admin only: `"nodeAttrs": [{"target": ["tag:k8s"], "attr": ["funnel"]}]`.

## Deploy a new build

The convergence repository's `image` workflow pushes
`ghcr.io/mwest2020/convergence-{server,web}:sha-<commit>` on main. Update both
digests in `deployment.yaml`; Argo CD rolls the pod. Because of `Recreate`, a
rollout is a short outage and resets the game world.

## Verify

```bash
kubectl -n convergence get pods                      # convergence 2/2, convergence-tunnel ×2
kubectl -n convergence logs -l app=convergence-tunnel --tail=20
curl -sI https://convergence.westerweel.work/        # 200 from nginx
```

The tunnel uses the same construction as netnl's: two cloudflared replicas
(anti-affinity `preferred`), DNS over TCP and `--protocol http2` instead of
QUIC. An HTTP 530 means no connector is up; see *HTTP 530 op
`api.westerweel.work`* in the [runbooks index](./index.md).

## Out-of-band

The packages are private, so the namespace needs the `ghcr-pull` secret,
copied from `agents` (command in `cluster-config/infra/convergence/README.md`;
jumpy has no `jq`, so it uses python3).
Without it the pod stays in `ImagePullBackOff`. The tunnel token is the
out-of-band Secret `convergence-tunnel`.
