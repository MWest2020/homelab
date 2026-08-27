# Change: remove-cluster-minio

> Besluit Mark 2026-08-27: "doe de nextcloud-migratie ook, dan minio eruit."
> Vervolg op `2026-08-27-migrate-wordsworth-s3-seaweedfs` (gearchiveerd).

## Why

MinIO OSS is gearchiveerd (2026-04-25, geen security-updates). De cluster-MinIO
had twee buckets: `wordsworth` (op 2026-08-27 gemigreerd naar SeaweedFS,
414 objecten checksum-gelijk, e2e-geverifieerd) en `nextcloud` — die bleek
**leeg (0 objecten)**: nextcloud-platform (`apps/infrastructure/
nextcloud-platform.yaml`, repo Nextcloud-base) is nooit op het cluster
ge-applied (zelfde patroon als de root-app). Er valt dus niets te migreren
voor Nextcloud en niets houdt MinIO nog in leven.

## What changes

- Cluster: Argo CD-Application `minio` verwijderen (finalizer ruimt de
  helm-resources incl. PVC 50Gi op), daarna namespace `minio` weg.
- Git: `apps/infrastructure/minio.yaml` en `cluster-config/infra/minio/`
  verwijderen; CHANGELOG-regel toevoegen.
- Vooraf: sanity-check dat wordsworth op SeaweedFS gezond is (health +
  objectaantal) — de MinIO-kopie is daarna bewust wegwerpbaar.

## Out of scope / follow-ups

- **Toekomstige Nextcloud-deploy**: moet naar SeaweedFS wijzen (S3-config zit
  in de Nextcloud-base-repo; aanpassen op het moment van echte deploy).
- **buzz-relay** draait een eigen MinIO in docker-compose op de VM
  (image-pin `RELEASE.2025-09-07`, los van het cluster). Zelfde
  archived-OSS-probleem, aparte afweging — hier alleen geflagd.

## Verification

`wordsworth /health` ok en search werkt ná verwijdering; geen namespace
`minio`, geen minio-PVC's; `grep -r minio cluster-config/ apps/` leeg.
