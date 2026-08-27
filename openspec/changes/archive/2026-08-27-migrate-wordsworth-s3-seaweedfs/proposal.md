# Change: migrate-wordsworth-s3-seaweedfs

> Besluit Mark 2026-08-27: "seaweed it is. speccen en migreren. bye minio
> wanneer het kan." Uitvoering door Claude, direct op main (thuislab-mandaat).

## Why

MinIO's open-source-editie is dood: binaries/images gestopt oktober 2025, repo
"no longer maintained" per 2026-02-12 en gearchiveerd op 2026-04-25 — geen
security-updates meer. De wordsworth-repo verbiedt MinIO daarom expliciet
(`CLAUDE.md`: "use Ceph RGW or SeaweedFS behind the S3 seam"), maar de
GitOps-wiring van 2026-08-12 wees `WORDSWORTH_S3_ENDPOINT_URL` pragmatisch naar
de bestaande MinIO (daar in maart neergezet voor Nextcloud). Daarmee staan de
(gepseudonimiseerde) documenten van wordsworth op een unmaintained store, in
strijd met het eigen dependency-beleid. SeaweedFS is al CI-bewezen in
wordsworth (testsuite draait tegen `chrislusf/seaweedfs:4.39` S3-gateway).

## What changes

- Nieuw: `cluster-config/infra/seaweedfs/` (Deployment `weed server -s3`,
  PVC 20Gi, ClusterIP :8333) + Argo CD `Application` op sync-wave 2 (zelfde
  wave als minio; wordsworth op wave 6 wacht er dus op).
- S3-credentials: identity-config als out-of-band Secret
  `seaweedfs/seaweedfs-s3-config` (nooit in Git), met dezelfde access/secret
  keys als het bestaande `wordsworth/wordsworth-s3`-secret zodat alleen het
  endpoint hoeft te wisselen.
- Datamigratie: eenmalige rclone-sync van bucket `wordsworth`
  (minio → seaweedfs), daarna verificatie op objectaantal.
- Flip: `WORDSWORTH_S3_ENDPOINT_URL` in
  `cluster-config/infra/wordsworth/configmap.yaml` naar
  `http://seaweedfs.seaweedfs.svc.cluster.local:8333` + rollout-restart api.

## Out of scope

- **MinIO opruimen kan nog niet**: Nextcloud gebruikt MinIO als primaire
  S3-store (`cluster-config/infra/minio/values.yaml`). "Bye minio" volgt pas
  na een aparte Nextcloud-migratie; tot die tijd blijft de minio-Application
  staan. De sync-wave-annotatie bij wordsworth verliest wel de minio-verwijzing.
- Ceph RGW (het lange-termijndoel in wordsworth `CLAUDE.md`) — SeaweedFS is de
  gesanctioneerde tussenstap; de S3-seam maakt een latere swap identiek aan deze.
- WORM/Object-Lock voor audit-export: niet geconfigureerd in de huidige deploy;
  apart te beoordelen (SeaweedFS-ondersteuning verifiëren vóór inschakelen).

## Verification

Wordsworth `/health` ok na de flip; bestaand document opvraagbaar (S3-read);
nieuwe ingest slaagt (S3-write); objectaantal seaweedfs-bucket ≥ minio-bucket;
geen referenties naar `minio.minio.svc` meer in wordsworth-config.
