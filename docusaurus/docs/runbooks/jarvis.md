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
  from the operator's proxy pod for this Service (namespace `tailscale` plus
  the labels `tailscale.com/parent-resource=jarvis`, `-ns=jarvis`,
  `-type=svc`). The namespace alone would also admit the public Funnel
  proxies of convergence and netnl. Egress: DNS and 443 only. Kubelet probes
  come from the node. The pod mounts no service-account token and gets no
  Service env vars.
- **Claude Code** runs every turn with `--restricted` and `Read(//proc/**)`
  denied, so its file tools stay in the project directory and out of the
  process environments (where the tokens are).
- **One pod, one replica, `Recreate`.** The init container `sync-projects`
  shallow-clones or refreshes **every repository MWest2020 owns** that the PAT
  can read (`JARVIS_SYNC_REPOS=*`, `JARVIS_SYNC_OWNER=MWest2020`) into the
  volume (`repos/`) at every start. The list comes from
  `GET /user/repos?affiliation=owner`, filtered on the owner's login, so an
  organisation's repositories are never cloned. Archived repos, forks and repos
  over 500 MB are skipped, each with a log line. The PAT is only in the init
  container. The bridge mounts `repos/` read-only at `/work` and serves every
  checkout there (`JARVIS_PROJECTS=*`, `JARVIS_PROJECTS_ROOT=/work`); Claude
  Code runs with `Read`, `Glob`, `Grep` only.
- **State** (`state/` on the same volume): the bridge's session file and log
  (`/state/jarvis`) and Claude Code's home (`/state/home`, with the session
  transcripts `--resume` needs). A restart keeps every project's conversation.
- **Memory:** about 1.8 GB resident (torch, faster-whisper base, Kokoro);
  requests 3Gi, limit 4Gi (measured 2026-11-14: 2.3 GiB at rest, peak 2.8 GiB). Prefers node-03, then node-02. The `local-path`
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
kubectl -n jarvis logs deploy/jarvis -c sync-projects      # "sync: <repo> refreshed to <sha>", skips, "N repositories available"
kubectl -n jarvis logs deploy/jarvis -c bridge | head       # the BEHIND_TAILSCALE_PROXY warning, then "listening"
kubectl -n tailscale get pods -l tailscale.com/parent-resource=jarvis   # the proxy the NetworkPolicy admits
# From a tailnet machine: no token must give 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST 'http://jarvis.tail8f7877.ts.net:8787/turn?project=jarvis'
```

`kubectl logs` shows request lines, summaries and errors only. The transcripts
and full replies are in `/state/jarvis/bridge.log` in the pod (rotated at
10 MB, three old files); only a summary is ever spoken. Both redact the
phone's token and the Claude credentials.

If the proxy is ever recreated with other labels (an operator upgrade, a
ProxyGroup), the tailnet gets timeouts: compare
`kubectl -n tailscale get pods --show-labels` with the podSelector in
`networkpolicy.yaml`.

## Projects

Every MWest2020 repository the PAT `pat-node-01` can read, except archived
ones, forks and repos over `JARVIS_SYNC_MAX_KB` (500 MB). On 2026-11-15 that
was 61 repos, 484 MB by the API's `size`, 411 MB of checked-out files; none
over the size limit. The phone gets the list from `GET /projects`.

- **Keep a repo off the phone:** add its name to `JARVIS_SYNC_EXCLUDE`
  (space-separated) in `deployment.yaml`. The next start removes its copy.
- **What happened at the last start:**
  `kubectl -n jarvis logs deploy/jarvis -c sync-projects`: one line per
  synced repo, one per skip (archived, fork, excluded, too large), then
  `N repositories available`.
- **Failures:** a repo that can't be refreshed keeps its old copy; a first
  clone that fails is logged and skipped; the init container fails only when no
  repo is available at all. If the GitHub API can't be reached, the copies
  already on the volume are refreshed and kept. Egress stays DNS and 443.
- **The first start** after switching to all repos clones everything, a few
  minutes; later starts only fetch.
- **Disk:** a shallow copy takes about twice its checked-out tree, so ~0.9 GB
  now. The PVC says 5Gi, but `local-path` doesn't enforce that and can't
  resize a PVC: the limit is the free disk on the node that holds the volume
  (`df -h /work` in the pod; 17 GB free on 2026-11-15). If that runs low, move
  to a new PVC (new name, same mounts). The copies are disposable and the init
  container re-clones them; copy `state/` across to keep the sessions.
- **Check the list over the tailnet** (with the phone's token):
  `curl -H "Authorization: Bearer $JARVIS_TOKEN" http://jarvis.tail8f7877.ts.net:8787/projects`
