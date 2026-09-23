---
title: Argo CD — forcing a sync and proving a rollout
sidebar_position: 2
---

# Argo CD — forcing a sync and proving a rollout

The cluster is GitOps: every Application syncs from this repo
(`cluster-config/infra/<app>`, branch `main`) with
`automated: {prune: true, selfHeal: true}`. A `kubectl set image` is drift and
gets reverted. Deploying means bumping the pin in the manifest and pushing.

## Forcing a sync without the argocd CLI

The CLI on jumpy has no server address. Patch the Application with an
`operation` block instead; Argo CD then runs a real sync, hooks included:

```bash
kubectl -n argocd patch applications.argoproj.io <app> --type merge \
  -p '{"operation":{"initiatedBy":{"username":"<you>"},"sync":{"syncStrategy":{"hook":{}}}}}'
```

You need this when a commit touches **only a hook manifest** (a PreSync
init-Job, a PostSync Job): that produces no resource diff, so Argo CD starts no
sync operation and the hook never runs.

## `Synced` is not proof

Argo CD once reported `Synced` at a revision it had not fetched: `reconciledAt`
was two minutes old and `sync.revision` pointed at the new commit, while
`summary.images` and the pod still carried the old digest. A hard refresh made
it show OutOfSync, after which the automated policy rolled it out:

```bash
kubectl -n argocd annotate application <app> argocd.argoproj.io/refresh=hard --overwrite
```

The reliable check is **the digest on the pod**, not what Argo CD says about
itself:

```bash
kubectl -n <ns> get deploy <app> -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl -n <ns> get pods -l app=<app> -o jsonpath='{..imageID}'
```

"Rolled out" is true only once the new pod is `1/1 Running` and the old one is
gone; the deployment spec changes earlier.

## Every image of an app moves together

A Job, CronJob or hook pinned separately from the Deployment silently keeps
running old code. It happened twice: wordsworth's init-Job stayed on an old sha
for months, so column migrations were never applied and every grant issue
returned 500 once the API moved on; netnl's prune CronJob stayed on the sha of
the app's creation, so a retention change never took effect — the job
succeeded, doing only the old work.

After a bump, sweep:

```bash
kubectl get cronjob,job,deploy -A -o wide | grep <app>
```

and compare every image of the app with its Deployment's.

## Pin to a digest, not `:latest`

`:latest` with `IfNotPresent` lets replicas drift apart when a pod lands on a
fresh node. Pin `image:tag@sha256:<digest>`. For a Deployment with
node anti-affinity and as many replicas as nodes, roll with
`maxSurge: 0, maxUnavailable: 1`: a surge pod would be unschedulable.
