---
title: Key backups (document_keys, OpenBao)
sidebar_position: 10
---

# Key backups: `document_keys` and OpenBao

Wordsworth seals originals with a data key per document (ADR-0008). The data
key is stored wrapped in the `document_keys` table; the wrapping key (the KEK,
Transit key `wordsworth`) lives only in OpenBao. Lose either and a sealed
original can never be opened again. These two backups are the deploy
precondition of wordsworth's `originals-ingest-switch` (wordsworth #379).

## What runs

| CronJob | Namespace | When (UTC) | What |
|---|---|---|---|
| `wordsworth-keys-backup` | `wordsworth` | 03:17 daily | `pg_dump --table=public.document_keys` (custom format) from `homelab-pg`, database `app` |
| `openbao-snapshot` | `openbao` | 03:27 daily | `bao operator raft snapshot save` |

Both write to the SeaweedFS bucket **`wordsworth-key-backups`**
(`document_keys/` and `openbao/`), each file with a `.sha256` next to it (the
dump also a `.rows` with its row count). Kept 30 days; each run deletes older
files.

**Why there:** OpenBao keeps its raft data on one `local-path` PVC on node-01,
and the Postgres primary is on node-02. The bucket has replication `001`, so
each file has a copy on two different nodes (node-01 and node-02 on
2026-11-05). That is off the OpenBao node and off the Postgres primary. It is
not off-cluster: see "Not covered" below.

Manifests: `cluster-config/infra/wordsworth/keys-backup.yaml`,
`cluster-config/infra/openbao/snapshot.yaml`.

## Secrets (out of band, never in git)

- `wordsworth-keys-backup` uses the existing `wordsworth-db` (database URL) and
  `wordsworth-s3`.
- `openbao-snapshot` uses the Secret `openbao-snapshot` in namespace `openbao`:
  - `BAO_TOKEN`: a periodic token (768h) with policy `openbao-snapshot`, which
    is only `path "sys/storage/raft/snapshot" { capabilities = ["read"] }`
    (plus OpenBao's `default`, for renew-self). Each run renews it.
  - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`: the SeaweedFS S3 identity.

  To recreate it (from jumpy; nothing is printed):

  ```sh
  R=$(kubectl -n openbao get secret openbao-keys -o jsonpath='{.data.root_token}' | base64 -d)
  B="kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=$R bao"
  printf 'path "sys/storage/raft/snapshot" { capabilities = ["read"] }' | $B policy write openbao-snapshot -
  T=$($B token create -policy=openbao-snapshot -period=768h -display-name=openbao-snapshot -field=token)
  AK=$(kubectl -n wordsworth get secret wordsworth-s3 -o jsonpath='{.data.WORDSWORTH_S3_ACCESS_KEY}' | base64 -d)
  SK=$(kubectl -n wordsworth get secret wordsworth-s3 -o jsonpath='{.data.WORDSWORTH_S3_SECRET_KEY}' | base64 -d)
  kubectl -n openbao create secret generic openbao-snapshot \
    --from-literal=BAO_TOKEN="$T" --from-literal=AWS_ACCESS_KEY_ID="$AK" --from-literal=AWS_SECRET_ACCESS_KEY="$SK"
  ```

A snapshot is encrypted with OpenBao's barrier key and opens only with the
unseal key (Secret `openbao-keys`). The unseal key is never written to the
bucket. The `document_keys` rows hold only wrapped keys, useless without the
KEK.

## Replication of the bucket

New buckets get the master's default placement (`000`). This one was set to
`001` on 2026-11-05, in `weed shell`:

```
lock
fs.configure -locationPrefix=/buckets/wordsworth-key-backups/ -replication=001 -apply
volume.configure.replication -collectionPattern=wordsworth-key-backups -replication=001
volume.fix.replication -collectionPattern=wordsworth-key-backups -apply
unlock
```

Check with `volume.list` that each `wordsworth-key-backups` volume shows on
two data nodes.

## Restore test

```sh
bash scripts/key-backups/restore-test.sh     # from jumpy
```

It makes a throwaway namespace and:

1. Downloads the newest dump and snapshot and checks their sha256.
2. Restores the dump into a throwaway Postgres and compares row count and
   columns with production. The table's foreign key to `documents` is left out
   there, because a table-only dump doesn't carry `documents`.
3. Has production wrap a random test value with the KEK now.
4. Starts a throwaway OpenBao, restores the snapshot (`-force`), unseals it
   with production's unseal key, reads the KEK's name and version, and
   unwraps the test value. `MATCH` means the snapshot can open what
   production wraps today.
5. Deletes the namespace.

It prints no key material.

**Result 2026-11-05:** both sha256 OK; `document_keys` restored with 0 rows
(production 0: sealing isn't live yet) and identical columns; snapshot
restored, KEK `wordsworth` latest_version 1 (production 1); unwrap **MATCH**.

Repeat the test after `originals-ingest-switch` is live, when the table has
rows, and after every KEK rotation.

## Restore for real

- **`document_keys` rows lost** (database intact): restore the rows into the
  `app` database, where `documents` exists, so the foreign key holds:
  `pg_restore --data-only --table=document_keys -d app <dump>`, against the
  primary. Rows that are still there conflict on the primary key: restore into
  a scratch table first and insert what is missing.
- **OpenBao lost** (PVC on node-01 gone): start OpenBao, `bao operator init`,
  unseal, then `bao operator raft snapshot restore -force <snap>` with that
  root token; it is sealed again afterwards with the barrier from the
  snapshot. Unseal with the key from `openbao-keys`. Production's root token
  and the wordsworth transit token are back as they were.

## Other secrets in OpenBao KV

Since 2026-11-07 OpenBao also has a KV v2 engine at `kv/`. It holds secrets
that are not cluster config but must not get lost, and the nightly
`openbao-snapshot` covers them too.

| Path | What | Lost? |
|---|---|---|
| `kv/bubbels/play-upload` | Bubbels' Google Play upload key: `keystore_b64` (PKCS12, alias `upload`), `store_password`, `key_alias`, `key_password`. Working copy on the agent host in `~/.config/bubbels/`. Upload certificate SHA-256 `8A:B3:BF:98:4E:80:A4:34:DB:E1:1F:D8:39:04:3F:7A:39:56:2C:76:13:27:5B:F6:2D:97:A6:D2:3E:44:02:02` | Not fatal: Google holds the app signing key (Play App Signing); the account owner requests an upload key reset in Play Console |

Read a value (from jumpy; the token is not printed):

```sh
R=$(kubectl -n openbao get secret openbao-keys -o jsonpath='{.data.root_token}' | base64 -d)
kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=$R \
  bao kv get -field=key_alias kv/bubbels/play-upload </dev/null
```

## Not covered

- **Off-cluster:** both copies are inside the cluster. A total cluster loss
  takes the sealed originals in SeaweedFS too, so the backup buys nothing
  there, but an off-cluster copy (jumpy, as for the SeaweedFS metadata) is the
  next step. jumpy has no passwordless sudo and no linger, so a reliable timer
  there needs Mark: `ansible-playbook` with `--ask-become-pass`.
- **The rest of the `app` database:** CNPG has no backup configured
  (`spec.backup` is empty). Only `document_keys` is dumped here.
