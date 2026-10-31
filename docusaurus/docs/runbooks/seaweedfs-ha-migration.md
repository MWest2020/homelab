---
title: SeaweedFS HA migration
sidebar_position: 9
---

# SeaweedFS HA migration (wordsworth#193 task 1.2)

One-off migration from the all-in-one SeaweedFS pod to a shape that survives
losing a node, node-01 included. Target manifests: homelab PR
[#32](https://github.com/MWest2020/homelab/pull/32), which is merged **at the
end** of the window, not before. Scripts: `scripts/seaweedfs-ha/`. Day-to-day
operation stays in [SeaweedFS](./seaweedfs.md).

**Window:** the night of Saturday 31 October to Sunday 1 November 2026, start
about 23:45 CET, hard stop 02:30 CET. Expected: about an hour. wordsworth (API
and console) is down during the window.

## What changes

| Piece | Today | After |
|---|---|---|
| master | 1, inside the all-in-one on node-01 | 3 in Raft, one per worker node |
| filer metadata (which S3 key is which file) | leveldb on node-01's volume | Postgres database `seaweedfs` on the CNPG cluster homelab-pg |
| filer + S3 gateway | 1, inside the all-in-one | 2 stateless pods, any node |
| volume servers | node-01 (all-in-one) + node-02 | node-01 (same volume, nothing copied) + node-02 + node-03 |

The document bytes don't move. The node-01 volume keeps the old leveldb
(`filerldb2/`) and master state (`m9333/`) untouched; that is the rollback.

## The five conditions (Mark, 2026-10-29)

### 1. How the master survives losing node-01

Three masters in Raft, one per worker node (required anti-affinity). Two of
three keep a leader. Measured in the rehearsal (below): the masters on the
other two nodes elected a new leader **48 seconds** after the leader's node was
cut off. The cut-off master rejoined as a follower when its node came back.
A fresh master needs no state from the old one: it learns the highest volume
id and file key from the volume servers' heartbeats (rehearsal:
`MaxVolumeId` correct right after start).

The rest of SeaweedFS also survives losing node-01:

- **Reads:** every volume has a copy on a second node (001).
- **Writes:** with three volume servers, a new volume still finds two servers
  to grow on. In the rehearsal, writes kept working with a node cut off.
- **Metadata:** the filers keep nothing locally; they read Postgres.

**Known limit, measured:** after a node goes away, the filers keep trying the
lost volume server first for a while before falling back to the copy. In the
rehearsal, 16 of 40 reads exceeded a 20-second client timeout in the first
minutes. Ten minutes in, it still happened now and then (1 of 40). A
`kubectl -n seaweedfs rollout restart deploy/seaweedfs-filer` cleared it:
40 of 40 reads, twice, with no dial timeouts after. So after losing a node:
restart the filers. That is degraded reads, not an outage; today, losing
node-01 means no S3 at all until node-01 is back.

### 2. Where CNPG runs; is a failover expected?

homelab-pg has 3 instances (CNPG 1.29.1, PostgreSQL 17): primary
`homelab-pg-1` on node-02, replicas `homelab-pg-2` on node-03 and
`homelab-pg-3` on node-01 (2026-10-31).

**No failover is expected.** The migration doesn't touch the CNPG pods. Adding
a managed role and a `Database` resource is done online by CNPG's instance
manager, without a restart; that is how the `keycloak` role and database were
added. The node-01 drill cuts off only SeaweedFS pods, not `homelab-pg-3`.
Go/no-go requires a healthy cluster with the primary on node-02.

After the migration, S3 depends on homelab-pg, as Keycloak already does. If the
primary's node goes away, CNPG promotes a replica and `homelab-pg-rw` follows.
The filers reconnect (connections are recycled every 300 s, and a failed one is
replaced). That path was **not** tested here; it is a separate drill.

### 3. Restore test of the filer metadata backup

Done on 2026-10-31 at 08:41 CET, read-only on the live system:

1. `fs.meta.save` on the live filer: 441 records (15 directories, 426 files),
   187,213 bytes, sha256 `3ebcd2ac…f942`. Copied off the pod, to jumpy and to
   the agent host (`~/seaweedfs-backup/`).
2. Loaded into a throwaway filer of the **target store type** (postgres2, own
   Postgres, own namespace) with `fs.meta.load`.
3. Compared every file under `/buckets/wordsworth` between live and restored
   through the filer's listing (path, size, md5, each chunk's file id, offset
   and size).

**First result: one file missing.** 422 of 423 files came back; the missing
one was the backup's last record. Cause, in the 4.39 source
(`weed/shell/command_fs_meta_load.go`): file records are written from
goroutines, and at the end of the stream the command returns without waiting
for them. The last insert races the shell's exit and is lost without an error.

**Fix, without a code change:** append a copy of the last directory record to
the backup ("sealing"). A directory record makes the loader wait for all
pending files first, and re-creating an existing directory is an idempotent
upsert. `cutover.sh backup` does this.

**Second result: identical.** 423 files and 522 chunks, byte-identical
listings (both sha256 `e9411b0a…211d`). This is the same check as the
cutover's `verify` step.

Also from the restore test: with the database's default collation
(en_US.utf8), the postgres2 store warns that S3 listings are not in byte order
and falls back to a slower sort. The target config declares the `name` column
`COLLATE "C"`. In the rehearsal the warning was gone.

### 4. Stop criteria, rollback, post-checks

See [Stop criteria](#stop-criteria), [Rollback](#rollback) and
[Post-checks](#post-checks) below.

### 5. The date

Saturday 31 October 2026, start about 23:45 CET (see Window).

## Rehearsal (2026-10-31)

The full migration, with the PR #32 manifests unchanged, in a throwaway
namespace `seaweedfs-rehearsal` with synthetic data. Postgres there was a
throwaway pod, standing in for CNPG, without TLS. It started in today's shape
(all-in-one + second volume server, bucket with 001, 40 random objects up to
9 MiB). It ran `cutover.sh` step by step, then `drill.sh` on a node, then
heal, then rollback.

| Step | Result |
|---|---|
| masters | Raft leader at once; `MaxVolumeId` learned from heartbeats |
| volume servers | every volume id with the same number of copies as before |
| metadata load + verify | both filers identical to the baseline (path, size, md5, chunks); filer.conf (the 001 rule) identical |
| S3 | 40/40 objects read back by md5; write + read back OK |
| node-loss drill (leader's node) | new leader after 48 s; writes OK; reads degraded until the filers were restarted (see condition 1) |
| heal | master rejoined as follower; 3 data nodes; every 001 volume with 2 copies; 40/40 |
| rollback A | all-in-one back from the untouched leveldb: identical to the baseline |

Second run, end to end with the final scripts (`rehearsal/rehearse.sh`,
08:21–08:27 UTC). All steps green: masters, volumes (a filer log volume grown
after the baseline is allowed and listed; every baseline volume must be back
with the same copies), load, verify on both filers, `readall` 40/40,
`writetest` OK. Drill on the node holding the old data volume, as node-01 will
tonight: a new leader within 60 s, `readall` and `writetest` clean before and
after the filer restart; heal clean. Through the filer (HTTP), reads did not
degrade in this run. The degraded reads of the first run were seen through
S3. So the filer restart stays in the drill, and the S3 probe as wordsworth
after resume (step 6) is the proof that counts.

## Procedure

Everything runs on jumpy, from a checkout of the PR branch:

```
cd ~/homelab && git fetch -q && git checkout -q seaweedfs-ha-manifests && git pull -q
kubectl kustomize cluster-config/infra/seaweedfs > ~/ha-target.yaml
cd scripts/seaweedfs-ha
C="./cutover.sh seaweedfs $HOME/ha-target.yaml"
```

Each `cutover.sh` step stops with `STOP: …` when its check fails. Evidence
lands in `scripts/seaweedfs-ha/evidence-seaweedfs/`.

### 0. Go / no-go (23:30)

All must hold, otherwise don't start:

- `kubectl -n cnpg-database get cluster homelab-pg`: healthy, 3/3 ready,
  primary `homelab-pg-1` (node-02).
- `kubectl -n argocd get app seaweedfs cnpg-database wordsworth`: Synced,
  Healthy.
- Disk on node-01/02/03 below 85 % (`df -h /` on the nodes).
- The S3 probe as wordsworth reads everything:
  `kubectl -n wordsworth cp s3probe.py <api-pod>:/tmp/ && kubectl -n wordsworth exec <api-pod> -- python /tmp/s3probe.py all`.
  It must say `bad=0`. Write down `objects=` and `bytes=`.
- No factory build running for wordsworth or homelab.

### 1. Freeze (23:45)

```
systemctl --user stop ratatoskr-agents          # on the agent host: no factory deploys in the window
for a in seaweedfs cnpg-database wordsworth; do
  kubectl -n argocd patch application $a --type merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
done
kubectl -n wordsworth scale deploy/wordsworth-api --replicas=0   # no writes from here on
```

### 2. Baseline and backup

```
$C baseline     # every file + chunk, volume list, filer.conf
$C backup       # fs.meta.save, copied off the pod, sealed; prints sha256
```

### 3. Postgres role and database

```
PW=$(openssl rand -hex 24)
for ns in cnpg-database seaweedfs; do
  kubectl -n $ns create secret generic seaweedfs-db --type=kubernetes.io/basic-auth \
    --from-literal=username=seaweedfs --from-literal=password="$PW"
done; unset PW
kubectl apply -n cnpg-database --validate=warn -k ~/homelab/cluster-config/infra/cnpg-database
kubectl -n cnpg-database get cluster homelab-pg -o jsonpath='{.status.managedRolesStatus.byStatus.reconciled}'   # contains seaweedfs
kubectl -n cnpg-database get database seaweedfs                                                           # APPLIED true
```

Both flags matter (found with a server-side dry-run on 2026-10-31):

- `-n cnpg-database`: the kustomization has no namespace (ArgoCD supplies it).
  Without the flag, the Database resources land in `default`.
- `--validate=warn`: `cluster.yaml` has `storage.storageClassName`, a field
  CNPG doesn't know (CNPG calls it `storageClass`). ArgoCD tolerates it; a
  strict `kubectl apply` refuses the whole Cluster. The fix is a separate
  change, not part of this window.

### 4. Cutover

```
$C stop-old       # all-in-one to 0 replicas; its volume untouched
$C apply-new      # masters, filers, volume servers, Services
$C wait-masters   # a Raft leader
$C wait-volumes   # every volume id with the same copies as the baseline
$C load           # sealed backup into the Postgres store
$C verify         # both filers identical to the baseline; filer.conf identical
$C readall        # every file read through a filer: md5/size
$C writetest      # write, read back, delete outside the buckets
```

Then give the filer log volume (collection `''`, replication 000, today only
on node-01) a second copy:

```
kubectl -n seaweedfs exec seaweedfs-master-0 -- sh -c 'printf "lock\nvolume.list\nunlock\n" | weed shell -master=seaweedfs-master:9333' | grep "Collection:,"
kubectl -n seaweedfs exec seaweedfs-master-0 -- sh -c 'printf "lock\nvolume.configure.replication -volumeId=<id> -replication=001\nvolume.fix.replication -apply\nunlock\n" | weed shell -master=seaweedfs-master:9333'
```

### 5. node-01 drill (writes still frozen)

```
./drill.sh seaweedfs node-01 isolate   # NetworkPolicy: SeaweedFS pods on node-01 cut off
# after 60 s: a leader on the other two masters
for m in $(kubectl -n seaweedfs get pod -l app=seaweedfs-master -o jsonpath='{.items[*].metadata.name}'); do
  kubectl -n seaweedfs exec $m -- wget -qO- -T 5 http://localhost:9333/cluster/status; echo; done
$C writetest
kubectl -n seaweedfs rollout restart deploy/seaweedfs-filer && kubectl -n seaweedfs rollout status deploy/seaweedfs-filer
$C readall; $C writetest
./drill.sh seaweedfs node-01 heal
# after 45 s: three masters, one leader; then
$C readall; $C writetest
kubectl -n seaweedfs exec seaweedfs-master-0 -- sh -c 'printf "lock\nvolume.fix.replication -verbose\nunlock\n" | weed shell -master=seaweedfs-master:9333' | grep -c "has 2 replicas"
```

The drill cuts off only SeaweedFS pods on node-01 (masters, the node-01 volume
server, a filer). Everything else on node-01 (Keycloak, OpenBao, Ollama,
ArgoCD, `homelab-pg-3`) keeps running, which a `kubectl drain` would not allow.

### 6. Resume

```
kubectl -n wordsworth scale deploy/wordsworth-api --replicas=1
kubectl -n wordsworth exec <api-pod> -- python /tmp/s3probe.py all   # bad=0, same objects= and bytes= as go/no-go
```

Writes are resumed from here; after this point, rollback is B, not A.

### 7. Make Git match

1. In PR #32, set the roadmap item "Storage survives a node" in
   `docs/reference/roadmap.yml` to `done`, with the #193 comment that reports
   the migration as evidence. Then merge PR #32.
2. Restore auto-sync:
   `kubectl apply -f apps/infrastructure/seaweedfs.yaml -f apps/infrastructure/cnpg-database.yaml -f apps/infrastructure/wordsworth.yaml`
   (on main).
3. ArgoCD prunes the scaled-down `seaweedfs` Deployment; the PVC stays. Wait
   until all three apps are Synced and Healthy.
4. Start the factory again: `systemctl --user start ratatoskr-agents`.

## Stop criteria

| When | Stop if | Then |
|---|---|---|
| go/no-go | CNPG not healthy or primary not on node-02; an app not Synced/Healthy; a node above 85 % disk; the probe has `bad>0` | don't start; new date |
| step 3 | role not reconciled or Database not applied within 5 min | Rollback A (nothing of SeaweedFS has changed yet) |
| any time | CNPG reports a switchover or failover | pause; `$C readall`; green → continue, otherwise Rollback A |
| `wait-masters` | no Raft leader within 5 min | Rollback A |
| `wait-volumes` | volume list differs from the baseline after 2 min | Rollback A |
| `load` / `verify` | load error, or any filer differs, or filer.conf differs | Rollback A |
| `readall` / `writetest` | any `bad`, or `FAIL` | Rollback A |
| drill | no leader on the other two masters within 2 min, or after the filer restart `readall`/`writetest` not clean | heal; Rollback A |
| resume | probe `bad>0` or objects/bytes differ from go/no-go | api to 0, Rollback A |
| clock | not at step 6 by 02:30 CET | Rollback A |

## Rollback

**A, before writes resume** (step 6). Nothing written since the baseline;
the old filer and master state are untouched on node-01's volume. About ten
minutes.

```
kubectl -n seaweedfs delete deploy seaweedfs-filer seaweedfs-volume-data
kubectl -n seaweedfs delete sts seaweedfs-master
kubectl -n seaweedfs delete svc seaweedfs-master-peers
kubectl -n seaweedfs delete cm seaweedfs-filer-config
git -C ~/homelab checkout -q main && kubectl apply -k ~/homelab/cluster-config/infra/seaweedfs
kubectl -n seaweedfs scale deploy/seaweedfs --replicas=1
kubectl -n seaweedfs rollout status deploy/seaweedfs && kubectl -n seaweedfs rollout status sts/seaweedfs-volume
```

Then:

1. Check that the old filer is identical to the baseline: walk it with
   `walk.py` (as in `cutover.sh baseline`) and `diff` against
   `evidence-seaweedfs/before-chunks.tsv`.
2. Restore auto-sync (step 7, without merging), scale the API to 1, run the
   probe, and start the factory.
3. The role, database and secret in CNPG can stay; they are unused.
4. The second new volume server's PVC (`data-seaweedfs-volume-1`, node-03)
   can be deleted.

Rehearsed: identical to the baseline.

**B, after writes resumed** (a problem found later). The new writes are only
in Postgres.

1. Freeze again (step 1).
2. Run `fs.meta.save` on a new filer and seal the file as in
   `cutover.sh backup`.
3. Move `filerldb2/` aside on node-01's volume (a one-off pod mounting
   `seaweedfs-data`), so the old filer starts empty.
4. Run Rollback A, but keep `seaweedfs-volume` at 2 replicas: new volumes may
   have their copies on node-02 and node-03.
5. `fs.meta.load` the sealed file into the all-in-one.
6. `volume.fix.replication -apply`.
7. Verify with a walk and the probe.

Not rehearsed.

## Post-checks

- Right after step 6: probe `all` as wordsworth, `bad=0`, same object count
  and bytes as at go/no-go.
- Right after step 7: ArgoCD seaweedfs, cnpg-database and wordsworth Synced and
  Healthy; `kubectl -n seaweedfs get pods -o wide` shows 3 masters on 3 nodes,
  3 volume servers on 3 nodes, 2 filers.
- The morning after: the console shows documents and a redacted PDF opens
  (Mark); the daily film check (06:43) passes its storage claims.
- After a week without problems: remove `filerldb2/` and `m9333/` from
  node-01's volume and the old PVC copies of the metadata backup; update
  [SeaweedFS](./seaweedfs.md) to the new shape.
