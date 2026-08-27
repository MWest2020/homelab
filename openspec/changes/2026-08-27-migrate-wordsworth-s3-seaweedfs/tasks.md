# Tasks: migrate-wordsworth-s3-seaweedfs

- [ ] 1. Manifests `cluster-config/infra/seaweedfs/` + `apps/infrastructure/seaweedfs.yaml` (sync-wave 2), commit + push
- [ ] 2. Out-of-band: namespace + Secret `seaweedfs-s3-config` (zelfde keys als `wordsworth-s3`), Argo-sync afwachten, pod Running
- [ ] 3. Bucket `wordsworth` migreren met rclone (minio → seaweedfs), objectaantal vergelijken
- [ ] 4. Configmap-flip naar seaweedfs-endpoint, commit + push, rollout-restart wordsworth-api
- [ ] 5. Verificatie: /health, document-read, ingest-write; sync-wave-annotatie minio-verwijzing weg
- [ ] 6. Change archiveren naar `openspec/changes/archive/`
