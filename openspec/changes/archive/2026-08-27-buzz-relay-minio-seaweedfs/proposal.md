# Change: buzz-relay-minio-seaweedfs

> Besluit Mark 2026-08-27: "pak de buzz-relay minio ook maar aan." Vervolg op
> remove-cluster-minio (gearchiveerd); zelfde reden, andere plek.

## Why

De buzz-relay-VM (boomhuis-communicatielaag, vm 109/.60) draait een eigen
MinIO in docker-compose als S3-store voor relay-media (`buzz-media`,
~644K: afbeeldingen + thumbnails + _meta). MinIO OSS is gearchiveerd
(2026-04-25) — geen security-updates; de gepinde image is van sept 2025.
SeaweedFS is elders in het ecosysteem al de gesanctioneerde vervanger
(cluster-migratie vandaag) en de relay praat via generieke S3-env
(`BUZZ_S3_ENDPOINT` + path-style), dus de swap raakt upstream-gedrag niet.

## Sanctioned deviation van de vendoring-regel

`docker/buzz-relay/docker-compose.yml` is vendored verbatim van block/buzz
(@4baccd53) met de regel "niet lokaal aanpassen". Deze change wijkt daar
bewust van af (sanctie: Marks opdracht 2026-08-27; precedent: de
cpu-type-uitzondering van 2026-07-06). De afwijking is gemarkeerd in de
file-header en beperkt tot: minio/minio-init → seaweedfs/seaweedfs-init +
`BUZZ_S3_ENDPOINT`. Bij een upstream-upgrade: nieuwe kopie nemen en deze
gemarkeerde afwijking opnieuw aanbrengen.

## What changes

- Compose: `minio` + `minio-init` vervangen door `seaweedfs`
  (chrislusf/seaweedfs:4.39, `weed server -s3`, identity uit bestaande
  `BUZZ_S3_ACCESS_KEY`/`SECRET` — geen nieuwe secrets) + `seaweedfs-init`
  (rclone, bucket aanmaken); relay-`depends_on` en `BUZZ_S3_ENDPOINT`
  (→ `http://seaweedfs:8333`) mee; volume `buzz-seaweedfs-data`.
- VM-uitvoering: seaweedfs ernaast starten → rclone `--checksum`-sync
  minio→seaweedfs → `compose up -d --remove-orphans` (flipt relay, ruimt
  minio-containers) → verificatie → tgz-backup van het minio-volume →
  volume weg.
- Playbook-/inventory-commentaar: MinIO-vermelding → SeaweedFS.

## Out of scope / follow-up

- De cpu-type=host-uitzondering (MinIO's glibc x86-64-v2-eis, CHANGELOG
  2026-07-06) kan hierna in principe terug naar het default cpu-type —
  SeaweedFS is een statische Go-binary. Vergt een VM-herstart; apart moment.

## Verification

Relay healthy na de flip; bestaand media-object opvraagbaar via de relay;
nieuwe S3-writes werken; objectaantallen src=dst bij rclone check; geen
minio-containers/volume meer op de VM.
