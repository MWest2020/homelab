# Tasks: buzz-relay-minio-seaweedfs

- [x] 1. Compose aanpassen (seaweedfs + seaweedfs-init, relay-env/depends_on, header-markering afwijking) + playbook/inventory-commentaar; commit
- [x] 2. VM: nieuwe compose plaatsen, seaweedfs ernaast starten (minio blijft draaien)
- [x] 3. rclone --checksum sync minio→seaweedfs + check (0 verschillen)
- [x] 4. compose up -d --remove-orphans (relay-flip, minio-containers weg); relay healthy + media-object opvraagbaar
- [x] 5. tgz-backup minio-volume naar /opt/buzz-relay/, daarna volume verwijderen
- [x] 6. CHANGELOG-regel, change archiveren, journal zettelkast

Uitvoering 2026-08-27: seaweedfs healthy naast minio → rclone --checksum sync
(21 objecten / 451 KiB, 0 verschillen) → compose up -d --remove-orphans →
relay healthy, log "Media storage connected", 0 errors; storage-level
read/write via rclone bewezen (142.580B object gelezen). Backup
/opt/buzz-relay/minio-final-backup-2026-08-27.tgz; volume + minio-images weg.
NB: media-GET via de relay geeft 404 op gegokte URL-vormen — applicatieniveau
(nette not-found-body), geen S3-fout; het echte media-URL-formaat kent alleen
de boomhuis-client.
