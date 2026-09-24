# buzz-relay — verhuisd

De stack van de relay-VM (Ratatoskr: relay, chat, postgres, redis, seaweedfs)
staat niet meer hier. Bron sinds 2026-09-11:
[MWest2020/ratatoskr `deploy/`](https://github.com/MWest2020/ratatoskr/tree/main/deploy)
(`docker-compose.yml` en `.env.example`), uitgerold volgens
`docs/how-to/installeren.md` in die repo.

Hier bleef tot 2026-09-24 een oudere, vendored kopie staan, samen met de
systemd-unit `boomhuis-chat.service` van het pad daarvóór. Twee manieren om de
chat te draaien, waarvan één dood: die zijn weg (ratatoskr-change
`opruimen-na-migratie`).

`ansible/playbooks/deploy-buzz-relay.yml` richt alleen nog de host in (Docker,
`/opt/buzz-relay`).
