---
title: Architectuur
sidebar_position: 1
---

# Architectuur (huidige staat)

Een **3-node Proxmox-cluster** met een **HA-Kubernetes** erop, volledig op VM's.

## Proxmox-laag

- 3 fysieke nodes (mini-PC's, elk 8 vCPU / 32GB) → **px-01 (.11), px-02 (.12), px-03 (.13)**.
- Eén Proxmox-cluster (corosync), oneven quorum → geen QDevice nodig.
- Storage: `local-lvm` per node. Templates per host (VMID's zijn cluster-breed uniek).

## Kubernetes-laag (v1.36)

- Per host **1 control-plane-VM + 1 worker-VM** (anti-affinity) → 3 CP + 3 workers.
- Control-plane-endpoint = **kube-vip VIP `192.168.178.201`** (HA).
- CP-VM's: `.202 / .203 / .204` · worker-VM's: `.205 / .206 / .207`.
- Verliest 1 fysieke machine → etcd-quorum (2/3) blijft → cluster leeft door.

## Capaciteit

- Per machine (32GB): 8GB CP-VM + 16GB worker-VM + ~8GB Proxmox-host.
- Workload-capaciteit = de 3 workers: **48GB RAM / 12 vCPU** (~40-45GB bruikbaar na overhead).
- De 3 CP's draaien geen app-workloads (getaint) — puur orchestratie.

## Platform-stack

- **Cilium** (eBPF CNI, kubeProxyReplacement, Gateway API).
- **MetalLB** (L2, pool `192.168.178.220-230`).
- **cert-manager** (Let's Encrypt DNS-01, wildcard `*.westerweel.work`).
- **Argo CD** (GitOps). Elke Application onder `apps/infrastructure/` is los
  ge-applied en synct daarna automatisch uit Git; de root-Application
  (`apps/root-app.yaml`) bestaat wel in de repo maar is **nooit gebootstrapt** (zie
  [Runbooks](../runbooks/)). Van de bredere Argo-suite staan **Workflows**,
  **Rollouts** en **Events** wél als manifest in de repo
  (`kubernetes/infrastructure/argo-*`, met een Application in
  `apps/infrastructure/`), maar ze zijn **niet uitgerold**: Argo CD kent er geen
  Application voor en de namespaces bestaan niet op het cluster.
- **local-path-provisioner** (default StorageClass, lokale disks per worker).
- **CloudNativePG** (PostgreSQL-operator) + **SeaweedFS** (S3-compatibele object
  storage — verving MinIO toen diens open-source-editie gearchiveerd werd, zie
  [Beslissingen](../beslissingen/)).
- **Tailscale-operator** (tailnet-interne exposure van Services, zonder publieke route).

## Data & AI-laag: de Wordsworth-straat

Een RAG-stack (retrieval-augmented generation) die **volledig in-cluster** draait —
documenten, embeddings en LLM-antwoorden verlaten het lab niet. Alle onderdelen zijn
Argo CD-apps, geordend met sync-waves zodat operators en storage vóór hun afnemers komen:

| Wave | Component | Rol |
|------|-----------|-----|
| 2 | CNPG-operator, Tailscale-operator, SeaweedFS | operators + object storage |
| 3 | OpenSearch, Ollama, OpenAnonymiser, OpenBao | zoekindex, lokale modellen, PII-detectie, key store |
| 4 | `homelab-pg` (CNPG Cluster) | PostgreSQL 17, 3 instances |
| 6 | Wordsworth API | RAG-API (ingest / search / hybrid / ask) |

- **Ollama** (CPU-only, geen GPU): `bge-m3`-embeddings (1024-dim) + `llama3.2:3b` als
  RAG-LLM. **Twee instances** (StatefulSet, één per worker, harde anti-affinity, PDB
  `maxUnavailable: 1`), elk met de eigen modellen op een eigen local-path-volume; de
  `ollama`-Service verdeelt over beide. Een init-container pullt de modellen per pod
  en vergelijkt ze met een **digest-pin**: wijkt een model af, dan start de pod niet.
- **OpenSearch** (2.19, **cluster van drie nodes** sinds 2026-09-26): hybride
  zoekindex. StatefulSet `opensearch-cluster`, één pod per worker, elk met een eigen
  local-path-volume; OpenSearch repliceert de shards zelf. Parallelle start (geen node
  is ready vóór er een quorum is), PDB `maxUnavailable: 1`. Security-plugin uit — alleen
  in-cluster bereikbaar (ClusterIP). De oude single-node (`opensearch`) blijft tot
  2026-10-03 staan als rollback.
- **OpenAnonymiser**: PII-detectie over HTTP (GLiNER, CPU-only); het model zit in de
  image gebakken, geen runtime-download. Draait met **3 replica's, één per worker**
  (harde anti-affinity): Wordsworth hakt documenten in chunks en waaiert die over de
  replica's uit, zodat de hele cluster-CPU meewerkt in plaats van één core.
- **OpenBao** (2.2, single-node raft): soevereine key store. Houdt de Transit-KEK die
  Wordsworths data-keys wrapt (reversibele pseudonimisering); de KEK verlaat OpenBao
  nooit. Alleen in-cluster bereikbaar, non-root, en **sealed-by-design** — initialisatie
  gebeurt out-of-band door de operator (zie [Runbooks](../runbooks/)).
- **Wordsworth API**: gehardende pods (non-root, read-only rootfs, alle capabilities
  gedropt), **2 replica's op twee nodes** (harde anti-affinity), image gepind op
  **digest** (`@sha256:…`), niet op een tag; het DB-schema
  wordt idempotent aangemaakt door een Argo CD PreSync init-Job. Sinds **Fase B** staat reversibele pseudonimisering aan:
  PII wordt vervangen door pseudoniemen waarvan de data-keys OpenBao-Transit-wrapped in
  de database liggen — herleidbaar voor wie dat mag, betekenisloos voor de rest.
- **PostgreSQL**: CNPG-cluster `homelab-pg` — PG17 (digest-gepind), 3 instances met
  anti-affinity over de workers; app-credentials genereert de operator zelf.
- **Object storage**: SeaweedFS (`weed server -s3`, ClusterIP `:8333`) is de S3-store
  voor de documenten — de data is in augustus 2026 checksum-geverifieerd gemigreerd
  vanaf MinIO (zie [Archief](../archief/)).
- **Caller-auth (opt-in)**: API-keys via het out-of-band Secret `wordsworth-apikeys`.
  Daarnaast een **EUDI-VC reveal-gate** (TEST-issuer, `REQUIRED=false`): een aangeboden
  verifiable credential versmalt een reveal tot grant ∩ VC-geautoriseerde types; zonder
  VC blijft reveal puur grant-gebaseerd. Twee label-scopes versmallen de kring
  bovendien per caller-label: alleen `console` en `cli` mogen de volledige
  de-identified tekst lezen (`WORDSWORTH_CORPUS_READ_LABELS`) en reveal-grants
  uitgeven of intrekken (`WORDSWORTH_GRANT_ISSUER_LABELS`).
- **Toegang via de tailnet**: via de Tailscale-operator, op twee manieren naast de
  gewone ClusterIP-Service: een http-`:8000`-LoadBalancer
  (`loadBalancerClass: tailscale`) voor de CLI, en een **tailnet-private HTTPS-Ingress**
  (MagicDNS-cert, bewust zónder Funnel-annotatie) voor de browser-based **Wordsworth
  Console** (GitHub Pages) — https is daar nodig omdat de browser een http-API als
  mixed content blokkeert. CORS staat opt-in open voor alleen die Console-origin.
- **Publieke demo-console** (sinds 2026-09-17): `wordsworth.westerweel.work` via een
  Cloudflare Tunnel (2 cloudflared-replica's, zelfde instellingen als netnl) naar
  **oauth2-proxy** (`wordsworth-auth`, 2 replica's). De proxy doet de OIDC-login bij
  Keycloak en geeft het ID-token door; Wordsworth verifieert het en schrijft het
  e-mailadres als caller in het auditspoor. Alleen dit publieke pad loopt via de proxy —
  de tailnet-ingangen gaan direct naar de API, met API-keys. Publiek omdat de corpora
  hier al gepubliceerde (Woo-)informatie zijn; wie met gevoelige data werkt, draait
  Wordsworth zelf.

## Publieke edge: de netnl-facade

Een publieke **batch-API-facade voor Internet.nl-metingen** — een onafhankelijke
instance, geen onderdeel van internet.nl of Platform Internetstandaarden. Code en
design: [MWest2020/internetnl-cli](https://github.com/MWest2020/internetnl-cli).

```
internet ──▶ Tailscale Funnel   (netnl.<tailnet>.ts.net) ─┐
internet ──▶ Cloudflare Tunnel  (api.westerweel.work)     ─┤─▶ Service netnl:8000
                                                           │   (facade, dit cluster)
                                                           ▼   HTTP Basic per tenant
                                     VPS-batch-instance (tailnet-only)
```

- De **facade** draait in-cluster (Argo CD-app, sync-wave 7, image digest-gepind);
  de echte **batch-instance** draait op een VPS met vast publiek IPv4+IPv6 — een
  ge-NAT homelab kan die niet hosten — en is uitsluitend via de tailnet bereikbaar.
- **Twee publieke ingangen** naar dezelfde facade: een Tailscale Funnel én een
  Cloudflare Tunnel voor de merknaam `api.westerweel.work` (run-token in het
  out-of-band Secret `netnl-tunnel`, ingress-regels remotely-managed bij Cloudflare).
  De cloudflared-pod draait met **2 replica's** (anti-affinity `preferred`): één
  tunnel-ID mag meerdere connectors hebben, dus vangt de ander het verkeer op terwijl
  de eerste herstart — anders is elke herstart een HTTP 530. cloudflared verbindt
  bewust over **TCP** (`--protocol http2`, DNS via `use-vc`) in plaats van QUIC/UDP,
  omdat het UDP-pad naar buiten niet betrouwbaar bleek (zie
  [Beslissingen](../beslissingen/)).
- **Egress** naar de VPS loopt via een Tailscale-operator-egress-Service; een
  CoreDNS-rewrite wijst `netnl.westerweel.work` in-cluster naar die Service, omdat de
  instance-nginx strikte SNI doet en het certificaat voor precies die naam serveert.
- Elke meet-route vereist **HTTP Basic per tenant**; een `netnl-prune`-CronJob (elke
  10 min) ruimt verlopen requests en oude audit-rows op.
- **Dagelijkse showcase-meting** (`netnl-measure`-CronJob, 05:17 UTC): meet drie eigen
  hostnames via het **publieke** endpoint — dezelfde weg als een echte tenant, inclusief
  tunnel en facade — en publiceert het resultaat naar de demo-repo
  `MWest2020/internetnl-cli-demo`. Twee containers, bewust gescheiden: een
  initContainer meet met de ongewijzigde CLI, een publish-container met git+ssh duwt
  de artefacten weg. Zo blijft de deploy key uit de meet-container.

## Wanderer: soevereiniteitsscanner

**Wanderer** meet de extern zichtbare voetafdruk van Nederlandse publieke organisaties:
passieve waarnemingen (RDAP, DNS, TLS, één HTTPS-GET per pad, `security.txt`), niet te
onderscheiden van een gewone bezoeker. Het is een Argo CD-app (sync-wave 6), image
digest-gepind.

- **Eén replica, `Recreate`**: de staat is een SQLite-database op een RWO-volume
  (`wanderer-data`) en er mag nooit meer dan één schrijver zijn.
- **Geplande scans** uit de ConfigMap `wanderer-schedules`: vier publieke doelen, elk
  wekelijks, op uiteenlopende tijden. De scheduler beoordeelt elke geslaagde scan zelf.
- **Standards-feed** (CronJob, zondag): een Internet.nl-batch via de
  [netnl-facade](#publieke-edge-de-netnl-facade) op alleen de eigen hosts, gepost naar
  Wanderer — de server blijft de enige schrijver van de database.
- **GeoIP** uit DB-IP Lite, bij elke podstart opgehaald door een init-container;
  mislukt dat, dan start Wanderer zonder en scoren de geo-regels "onbekend".
- **Toegang**:
  - publiek `wanderer.westerweel.work` via een Cloudflare Tunnel, waarbij de
    ingress-regel **alleen `/ui`** doorlaat: de REST-API heeft geen authenticatie en
    mag nooit publiek bereikbaar zijn. De UI is alleen-lezen (scanformulier uit) en
    inloggen gaat via Keycloak (OIDC).
  - tailnet-intern via een Tailscale-Ingress (MagicDNS-cert): de volledige server, de
    REST-API inbegrepen, voor CLI- en operatorgebruik.

## Buzz-relay-VM (boomhuis-communicatielaag)

Naast het K8s-cluster, op de laptop-Proxmox-node: **VM 109 (`192.168.178.60`)** met een
zelf-gehoste [block/buzz](https://github.com/block/buzz)-relay (Nostr) als
communicatielaag voor het agent-ecosysteem (spec: `MWest2020/boomhuis`).

- **Tailnet + LAN-only**: `ws://` zonder publieke DNS/TLS — transport-encryptie komt
  van Tailscale; closed relay mode.
- Compose-stack (Ratatoskr: relay, chat, PostgreSQL, Redis, SeaweedFS als
  S3-mediastore) staat sinds 2026-09-11 in
  [MWest2020/ratatoskr `deploy/`](https://github.com/MWest2020/ratatoskr/tree/main/deploy),
  niet meer in deze repo. Het Ansible-playbook hier richt alleen de host in.

*(Per onderwerp volgen detail-pagina's; de freshness-agent houdt dit synchroon met de repo.)*
