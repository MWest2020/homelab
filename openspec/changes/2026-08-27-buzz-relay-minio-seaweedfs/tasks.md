# Tasks: buzz-relay-minio-seaweedfs

- [ ] 1. Compose aanpassen (seaweedfs + seaweedfs-init, relay-env/depends_on, header-markering afwijking) + playbook/inventory-commentaar; commit
- [ ] 2. VM: nieuwe compose plaatsen, seaweedfs ernaast starten (minio blijft draaien)
- [ ] 3. rclone --checksum sync minio→seaweedfs + check (0 verschillen)
- [ ] 4. compose up -d --remove-orphans (relay-flip, minio-containers weg); relay healthy + media-object opvraagbaar
- [ ] 5. tgz-backup minio-volume naar /opt/buzz-relay/, daarna volume verwijderen
- [ ] 6. CHANGELOG-regel, change archiveren, journal zettelkast
