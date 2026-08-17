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
- **CloudNativePG** (PostgreSQL-operator) + **MinIO** (S3-compatibele object storage).
- **Tailscale-operator** (tailnet-interne exposure van Services, zonder publieke route).

## Data & AI-laag: de Wordsworth-straat

Een RAG-stack (retrieval-augmented generation) die **volledig in-cluster** draait —
documenten, embeddings en LLM-antwoorden verlaten het lab niet. Alle onderdelen zijn
Argo CD-apps, geordend met sync-waves zodat operators en storage vóór hun afnemers komen:

| Wave | Component | Rol |
|------|-----------|-----|
| 2 | CNPG-operator, Tailscale-operator, MinIO | operators + object storage |
| 3 | OpenSearch, Ollama, OpenAnonymiser | zoekindex, lokale modellen, PII-redactie |
| 4 | `homelab-pg` (CNPG Cluster) | PostgreSQL 17, 3 instances |
| 6 | Wordsworth API | RAG-API (ingest / search / hybrid / ask) |

- **Ollama** (CPU-only, geen GPU): `bge-m3`-embeddings (1024-dim) + `llama3.2:3b` als
  RAG-LLM; modellen worden door een PostSync-hook-Job gepulld.
- **OpenSearch** (2.x, single-node): hybride zoekindex; security-plugin uit — alleen
  in-cluster bereikbaar (ClusterIP).
- **OpenAnonymiser**: PII-redactie over HTTP (spaCy `nl_core_news_lg`); het model zit in
  de image gebakken, geen runtime-download.
- **Wordsworth API**: gehardende pod (non-root, read-only rootfs, alle capabilities
  gedropt), image per commit-SHA gepind; het DB-schema wordt idempotent aangemaakt door
  een Argo CD PreSync init-Job.
- **PostgreSQL**: CNPG-cluster `homelab-pg` — PG17 (digest-gepind), 3 instances met
  anti-affinity over de workers; app-credentials genereert de operator zelf.
- **Toegang**: de API is **niet publiek** — tailnet-intern via de Tailscale-operator
  (`loadBalancerClass: tailscale`), naast de gewone ClusterIP-Service voor in-cluster
  verkeer.

*(Per onderwerp volgen detail-pagina's; de freshness-agent houdt dit synchroon met de repo.)*
