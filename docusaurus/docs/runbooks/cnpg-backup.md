---
title: CNPG backup (homelab-pg)
sidebar_position: 11
---

# CNPG backup: the whole `homelab-pg` cluster

`homelab-pg` (ns `cnpg-database`) holds the databases `app` (wordsworth),
`keycloak` and `seaweedfs` (the SeaweedFS filer metadata). Until 2026-11-08 it
had no `spec.backup` at all: only the `document_keys` table was dumped
([key backups](key-backups.md)).

## What runs

- **WAL archiving**, continuous, through barman-cloud (`spec.backup` in
  `cluster-config/infra/cnpg-database/cluster.yaml`).
- **A base backup every day at 03:37 UTC** (`scheduledbackup.yaml`), after the
  key backups at 03:17 and 03:27.
- **Retention 30 days** (`retentionPolicy: "30d"`); CNPG deletes older base
  backups and the WAL they no longer need.

Target: the SeaweedFS bucket **`homelab-pg-backups`**, replication `001` (each
file on two data nodes), set when the bucket was made:

```
lock
s3.bucket.create -name homelab-pg-backups
fs.configure -locationPrefix=/buckets/homelab-pg-backups/ -replication=001 -apply
unlock
```

Mechanism: CNPG's in-tree `barmanObjectStore`. CNPG 1.29.1 still supports it
and the `-system-` PostgreSQL image carries barman-cloud 3.19.1. **It is removed
in CloudNativePG 1.30.0** (the operator warns on every apply): do not upgrade
the operator to 1.30 before moving to the Barman Cloud plugin.

## Secret (out of band, never in git)

`homelab-pg-backup-s3` in `cnpg-database`, keys `ACCESS_KEY_ID` and
`ACCESS_SECRET_KEY`: the same SeaweedFS S3 identity as `wordsworth-s3`. To
recreate it from jumpy (nothing is printed):

```sh
AK=$(kubectl -n wordsworth get secret wordsworth-s3 -o jsonpath='{.data.WORDSWORTH_S3_ACCESS_KEY}' | base64 -d)
SK=$(kubectl -n wordsworth get secret wordsworth-s3 -o jsonpath='{.data.WORDSWORTH_S3_SECRET_KEY}' | base64 -d)
kubectl -n cnpg-database create secret generic homelab-pg-backup-s3 \
  --from-literal=ACCESS_KEY_ID="$AK" --from-literal=ACCESS_SECRET_KEY="$SK"
```

## Check that it works

```sh
kubectl -n cnpg-database get cluster homelab-pg \
  -o jsonpath='{.status.conditions[?(@.type=="ContinuousArchiving")].status}{"\n"}{.status.firstRecoverabilityPoint}{"\n"}{.status.lastSuccessfulBackup}{"\n"}'
kubectl -n cnpg-database get backups
```

`ContinuousArchiving` must be `True`, and the last backup `completed`.

An extra backup on demand:

```sh
kubectl -n cnpg-database apply -f - <<'EOF'
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: homelab-pg-ondemand-YYYYMMDD
  namespace: cnpg-database
spec:
  method: barmanObjectStore
  cluster:
    name: homelab-pg
EOF
```

## Restore test (throwaway namespace)

1. Copy the secret into a throwaway namespace (`cnpg-restore-test`).
2. Create a Cluster there with `bootstrap.recovery.source` pointing at an
   `externalClusters` entry with the same `barmanObjectStore` and
   `serverName: homelab-pg`. Use **one** instance, no `spec.backup` (a test
   cluster must never archive into the production path), and a small PVC.
3. Compare per database: the table count, and `count(*)` per table in `app`,
   against the live cluster.
4. Delete the namespace.

**First base backup after enabling archiving:** wait until a WAL file has
really reached the bucket (`fs.ls /buckets/homelab-pg-backups/homelab-pg/wals/`)
before the first backup. On 2026-11-08 the first on-demand backup started at
WAL `…D9`, which had still been "archived" by CNPG's no-op archiver before
`spec.backup` took effect. That backup cannot be restored ("WAL not found");
the second one, started at `…DC`, can. Retention removes the broken one after
30 days.

### Result 2026-11-08

| Step | Result |
|---|---|
| WAL archiving | `ContinuousArchiving=True`; WAL `…DA` onwards in the bucket |
| on-demand backup `20261108T093406` | completed in 11 s, WAL `…DC`–`…DD` |
| recovery into `cnpg-restore-test` (1 instance, 2Gi) | ready in 41 s |
| `app` | 17 tables, 90,233 rows, **identical per table** (incl. `audit_records` 8,767, `document_keys` 0) |
| `keycloak` | 89 tables, 2 users, same as live |
| `seaweedfs` | 5 tables; `filemeta` 44 vs 45 live: the newest backup object, written after the last archived WAL |

The throwaway namespace was deleted afterwards.

## Restore for real

Restore into a **new** cluster name (for example `homelab-pg-r1`), never over
the existing one:

1. Pause ArgoCD auto-sync for `cnpg-database`, `seaweedfs` and `wordsworth`,
   and scale `wordsworth-api` to 0.
2. Apply a Cluster `homelab-pg-r1` with `bootstrap.recovery` from
   `homelab-pg` in `homelab-pg-backups` (add `recoveryTarget.targetTime` for
   a point in time). Keep the same `managed.roles` and the same image.
3. When it is healthy: point the consumers at it (the `-rw` service name in the
   wordsworth, keycloak and seaweedfs filer configs, through a GitOps PR), or
   rename in git so `homelab-pg` is the restored one. Give the new cluster its
   own `spec.backup` with a new `serverName`, so it doesn't write into the old
   backup's path.
4. Resume, then check `/health`, the S3 probe and Keycloak login.

## Not covered

- **A circle:** the SeaweedFS filer keeps its metadata in this same cluster.
  Lose `homelab-pg` completely and the filer can no longer map the
  `homelab-pg-backups` keys to chunks. The chunks are still on the volume
  servers, but you first need the filer metadata back: an `fs.meta.save`
  snapshot (see the [HA migration](seaweedfs-ha-migration.md)) or a filer
  rebuilt from the volumes. The backup protects well against a lost
  instance, a lost node, a dropped table or a bad migration; against a total
  cluster loss it needs an off-cluster copy, the open gap already listed in
  [key backups](key-backups.md).
