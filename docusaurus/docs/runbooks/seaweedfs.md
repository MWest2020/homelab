---
title: SeaweedFS
sidebar_position: 8
---

# SeaweedFS

Object storage for wordsworth (S3, bucket `wordsworth`), Argo CD app
`seaweedfs` (sync-wave 2), manifests in `cluster-config/infra/seaweedfs/`.

## Shape (since 2026-10-28, wordsworth#193)

- `deployment.yaml`: the all-in-one pod (`weed server -s3`): master, filer,
  S3 gateway and the first volume server, on a local-path volume (node-01).
- `volume-statefulset.yaml`: a **second volume server** on another node
  (required anti-affinity, node-02 preferred), its own local-path volume.
- `master-service.yaml`: the master's ports (9333/19333), so the second volume
  server can join.

The `wordsworth` collection is replicated **`001`**: every wordsworth volume
has a copy on the other volume server, so the document bytes live on two
nodes.

## Set and repair replication (weed shell, imperative)

Replication is master and filer state, not a manifest. Run in the all-in-one
pod (`kubectl -n seaweedfs exec deploy/seaweedfs -- weed shell -master=localhost:9333`):

```
lock
fs.configure -locationPrefix=/buckets/wordsworth/ -replication=001 -apply
volume.configure.replication -collectionPattern=wordsworth -replication=001
volume.fix.replication -collectionPattern=wordsworth
volume.list
unlock
```

`fs.configure` makes new writes under the bucket land with `001`;
`volume.configure.replication` changes the existing volumes and
`volume.fix.replication` copies them. Copying only adds; the originals are not
touched. The copy runs inside the all-in-one pod: with a 1 GiB limit it was
OOM-killed on 2026-10-28 (the pod restarted; no data was lost, verified by
object count, bytes and ETags), so its limit is 2 GiB. Check afterwards with `volume.list` that each wordsworth volume shows
on both data nodes, and that the bucket's object count and bytes match what
they were before.

## What does NOT survive a node yet

The **filer metadata** (which S3 key is which file) is a leveldb on the
all-in-one pod's volume, and the **master** runs there too. If node-01 goes
away, the volume copies survive, but S3 cannot find them until the filer comes
back. Fixing that (filer store on the CNPG Postgres cluster, a master that can
restart elsewhere) is the next step of wordsworth#193 and needs a short planned
outage; it is Mark's call.

## Object Lock

SeaweedFS 4.39 enforces Object Lock (COMPLIANCE, GOVERNANCE, legal hold) in
its S3 gateway. Proof on this cluster: wordsworth#193 (2026-10-28). A test
object with COMPLIANCE retention cannot be deleted until its retain-until
date; use a short date (minutes) for a test so it can be cleaned up.

## Disk

Every worker's local-path volume sits on the node's OS disk (about 50 GB).
On 2026-10-28: node-01 82 % used, node-02 71 %, node-03 78 %. A volume server
takes as many 1 GB volume slots as its free disk allows at startup; when the
disk fills, new buckets and collections can no longer grow (that blocked the
Object Lock test on 2026-10-04).
