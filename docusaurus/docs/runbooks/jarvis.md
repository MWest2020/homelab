---
title: Jarvis
sidebar_position: 13
---

# Jarvis

The voice bridge from Mark's phone to headless Claude Code (MWest2020/jarvis,
`docs/how-to/run-in-cluster.md` there). **Tailnet only**, never public. Argo CD
app `jarvis` (sync-wave 7, after the tailscale-operator), manifests in
`cluster-config/infra/jarvis/`.

## Shape

- **Entry:** `http://jarvis.tail8f7877.ts.net:8787/turn?project=<name>`, with
  `Authorization: Bearer <token>` (the token Mark's phone has). A Service of
  type `LoadBalancer`, `loadBalancerClass: tailscale`, hostname `jarvis`, **no
  Funnel annotation**, and `allocateLoadBalancerNodePorts: false` (no
  NodePort on the LAN). Plain HTTP inside the tailnet, as the phone's HTTP
  Shortcuts button expects.
- **Only the proxy gets in:** the bridge listens on its pod IP
  (`JARVIS_BEHIND_TAILSCALE_PROXY=1`, `JARVIS_BIND_HOST` from the Downward
  API), and the NetworkPolicy `jarvis-tailscale-only` admits port 8787 only
  from namespace `tailscale` (the operator's proxy pod). Kubelet probes come
  from the node.
- **One pod, one replica, `Recreate`.** The init container `sync-projects`
  shallow-clones or refreshes wordsworth, bazibo, jarvis, convergence,
  ratatoskr and homelab into the volume (`repos/`) at every start, with
  `GIT_PAT`. The PAT is only in the init container. The bridge mounts
  `repos/` read-only at `/work`, and Claude Code runs with `Read`, `Glob`,
  `Grep` only.
- **State** (`state/` on the same volume): the bridge's session file and log
  (`/state/jarvis`) and Claude Code's home (`/state/home`, with the session
  transcripts `--resume` needs). A restart keeps every project's conversation.
- **Memory:** about 1.8 GB resident (torch, faster-whisper base, Kokoro);
  requests 2.5Gi, limit 3Gi. Prefers node-03, then node-02. The `local-path`
  volume pins the pod to the node where it first landed.
- **Probes:** TCP on 8787. The server only listens once both speech models
  are loaded; the startup probe allows ten minutes.

## Out-of-band secrets (namespace `jarvis`, never in Git)

| Secret | Key | Source |
|---|---|---|
| `claude-oauth-token` | `token` | copied from `agents` |
| `pat-node-01` | `GIT_PAT` | copied from `agents` |
| `ghcr-pull` | `.dockerconfigjson` | copied from `agents` (the package is private) |
| `jarvis-token` | `token` | `JARVIS_TOKEN` from the agent host's `~/.config/jarvis/env` (the phone has it) |

Copying from `agents` (from jumpy):

```bash
for s in claude-oauth-token pat-node-01 ghcr-pull; do
  kubectl get secret $s -n agents -o json \
    | python3 -c 'import json,sys; s=json.load(sys.stdin); s["metadata"]={"name":s["metadata"]["name"]}; print(json.dumps(s))' \
    | kubectl apply -n jarvis -f -
done
```

When the Claude token in `agents` is rotated, copy it again and restart:
`kubectl -n jarvis rollout restart deploy/jarvis`.

## New build

A merge to main in MWest2020/jarvis pushes
`ghcr.io/mwest2020/jarvis-bridge:<sha>`. Resolve the digest and pin it in
**both** places in `deployment.yaml` (init container and bridge):

```bash
docker buildx imagetools inspect ghcr.io/mwest2020/jarvis-bridge:<sha>
```

## Checks

```bash
kubectl -n jarvis get pods -o wide
kubectl -n jarvis logs deploy/jarvis -c sync-projects      # "sync: <repo> refreshed to <sha>"
kubectl -n jarvis logs deploy/jarvis -c bridge | head       # the BEHIND_TAILSCALE_PROXY warning, then "listening"
# From a tailnet machine: no token must give 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST 'http://jarvis.tail8f7877.ts.net:8787/turn?project=jarvis'
```

The full replies and transcripts are in `/state/jarvis/bridge.log` in the pod
(only a summary is ever spoken).

## Projects

The list is in two places in `deployment.yaml`: `JARVIS_SYNC_REPOS` (init
container, `owner/name`) and `JARVIS_PROJECTS` (bridge, `name=/work/name`).
Change both together. A repo that can't be cloned fails the init container.
