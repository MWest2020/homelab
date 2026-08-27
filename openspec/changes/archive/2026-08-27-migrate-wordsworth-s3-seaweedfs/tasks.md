# Tasks: migrate-wordsworth-s3-seaweedfs

- [x] 1. Manifests `cluster-config/infra/seaweedfs/` + `apps/infrastructure/seaweedfs.yaml` (sync-wave 2), commit + push
- [x] 2. Out-of-band: namespace + Secret `seaweedfs-s3-config` (zelfde keys als `wordsworth-s3`), Argo-sync afwachten, pod Running
- [x] 3. Bucket `wordsworth` migreren met rclone (minio → seaweedfs), objectaantal vergelijken
- [x] 4. Configmap-flip naar seaweedfs-endpoint, commit + push, rollout-restart wordsworth-api
- [x] 5. Verificatie: /health, document-read, ingest-write; sync-wave-annotatie minio-verwijzing weg
- [x] 6. Change archiveren naar `openspec/changes/archive/`

Uitvoering 2026-08-27: alle stappen voltooid. Migratie: 414 objecten / 1,662 GiB,
rclone --checksum, 0 verschillen. E2E na flip: ingest→indexed (4,9s) + search-hit
via SeaweedFS. NB: root-app bleek niet gebootstrapt op het cluster — de
seaweedfs-Application is los ge-applied, conform bestaande praktijk.
