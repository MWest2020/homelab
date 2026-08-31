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
- **Argo CD** (GitOps, app-of-apps: één root-Application beheert alle child-apps
  onder `apps/infrastructure/`).
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
  RAG-LLM; modellen worden door een PostSync-hook-Job gepulld.
- **OpenSearch** (2.x, single-node): hybride zoekindex; security-plugin uit — alleen
  in-cluster bereikbaar (ClusterIP).
- **OpenAnonymiser**: PII-detectie over HTTP (GLiNER, CPU-only); het model zit in de
  image gebakken, geen runtime-download. Draait met **3 replica's, één per worker**
  (harde anti-affinity): Wordsworth hakt documenten in chunks en waaiert die over de
  replica's uit, zodat de hele cluster-CPU meewerkt in plaats van één core.
- **OpenBao** (2.2, single-node raft): soevereine key store. Houdt de Transit-KEK die
  Wordsworths data-keys wrapt (reversibele pseudonimisering); de KEK verlaat OpenBao
  nooit. Alleen in-cluster bereikbaar, non-root, en **sealed-by-design** — initialisatie
  gebeurt out-of-band door de operator (zie [Runbooks](../runbooks/)).
- **Wordsworth API**: gehardende pod (non-root, read-only rootfs, alle capabilities
  gedropt), image per commit-SHA gepind; het DB-schema wordt idempotent aangemaakt door
  een Argo CD PreSync init-Job. Sinds **Fase B** staat reversibele pseudonimisering aan:
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
  VC blijft reveal puur grant-gebaseerd.
- **Toegang**: de API is **niet publiek** — tailnet-intern via de Tailscale-operator,
  op twee manieren naast de gewone ClusterIP-Service: een http-`:8000`-LoadBalancer
  (`loadBalancerClass: tailscale`) voor de CLI, en een **tailnet-private HTTPS-Ingress**
  (MagicDNS-cert, bewust zónder Funnel-annotatie) voor de browser-based **Wordsworth
  Console** (GitHub Pages) — https is daar nodig omdat de browser een http-API als
  mixed content blokkeert. CORS staat opt-in open voor alleen die Console-origin.

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
  Cloudflare Tunnel voor de merknaam `api.westerweel.work` (cloudflared-pod;
  run-token in het out-of-band Secret `netnl-tunnel`, ingress-regels remotely-managed
  bij Cloudflare).
- **Egress** naar de VPS loopt via een Tailscale-operator-egress-Service; een
  CoreDNS-rewrite wijst `netnl.westerweel.work` in-cluster naar die Service, omdat de
  instance-nginx strikte SNI doet en het certificaat voor precies die naam serveert.
- Elke meet-route vereist **HTTP Basic per tenant**; een `netnl-prune`-CronJob (elke
  10 min) ruimt verlopen requests en oude audit-rows op.

## Buzz-relay-VM (boomhuis-communicatielaag)

Naast het K8s-cluster, op de laptop-Proxmox-node: **VM 109 (`192.168.178.60`)** met een
zelf-gehoste [block/buzz](https://github.com/block/buzz)-relay (Nostr) als
communicatielaag voor het agent-ecosysteem (spec: `MWest2020/boomhuis`).

- **Tailnet + LAN-only**: `ws://` zonder publieke DNS/TLS — transport-encryptie komt
  van Tailscale; closed relay mode.
- Compose-stack **vendored verbatim** van upstream: relay + PostgreSQL 17 + Redis 7 +
  SeaweedFS als S3-mediastore (een gesanctioneerde, gemarkeerde afwijking van de
  vendored file — zie [Beslissingen](../beslissingen/)).

*(Per onderwerp volgen detail-pagina's; de freshness-agent houdt dit synchroon met de repo.)*
