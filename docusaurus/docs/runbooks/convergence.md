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

## Access

- **Public:** `https://convergence.tail8f7877.ts.net` through a Tailscale
  Funnel Ingress (same construction as netnl).
- `convergence.westerweel.work` follows when Mark adds the Cloudflare hostname.

## Deploy a new build

The convergence repository's `image` workflow pushes
`ghcr.io/mwest2020/convergence-{server,web}:sha-<commit>` on main. Update both
digests in `deployment.yaml`; Argo CD rolls the pod.

## Out-of-band

The packages are private, so the namespace needs the `ghcr-pull` secret,
copied from `agents` (command in `cluster-config/infra/convergence/README.md`).
Without it the pod stays in `ImagePullBackOff`.
