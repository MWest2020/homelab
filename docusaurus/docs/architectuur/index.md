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
- **Argo CD** (GitOps).

*(Per onderwerp volgen detail-pagina's; de freshness-agent houdt dit synchroon met de repo.)*
