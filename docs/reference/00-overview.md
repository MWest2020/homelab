---
status: draft
last_reviewed: 2026-07-12
---

# Homelab Overview

Dit document beschrijft het overzicht van de homelab infrastructuur.

## Doel

Een reproduceerbare homelab setup met:
- 3x HP EliteDesk Mini-PC's als Kubernetes nodes
- Infrastructure as Code via Ansible
- [**Kubernetes the Hard Way**](https://github.com/kelseyhightower/kubernetes-the-hard-way/tree/master) - handmatig opgezet voor maximaal begrip

## Quick Links

| Doc | Beschrijving |
|-----|--------------|
| [01 - Hardware](01-hardware.md) | Hardware specificaties |
| [02 - Network](02-network.md) | IP schema, netwerk diagram |
| [03 - Installation](../how-to/03-installation.md) | Ubuntu Server installatie |
| [04 - Post-install](../how-to/04-post-install.md) | Hardening, prepare nodes |
| [05 - Ansible](../how-to/05-ansible.md) | Ansible setup en playbooks |
| [06 - Kubernetes](../how-to/06-kubernetes.md) | Kubernetes the Hard Way |

## GitOps Journey

| Doc | Beschrijving |
|-----|--------------|
| [20 - Stappenplan](../how-to/20-stappenplan-gitops.md) | Master plan: CRDs → Gateway → Argo CD |
| [21 - Gateway API CRDs](../how-to/21-gateway-api-crds.md) | CRDs voor Gateway API |
| [22 - Cilium Gateway](../how-to/22-cilium-gateway.md) | Stap 2: commando's en checks |
| [23 - MetalLB](../how-to/23-metallb.md) | Stap 3: LoadBalancer IP's |
| [24 - cert-manager](../how-to/24-cert-manager.md) | Stap 4: TLS (Let's Encrypt, DNS-01) |
| [25 - Gateway TLS](../how-to/25-gateway-tls.md) | Stap 5: HTTPS Gateway + test |
| [30 - Migratie kubeadm](../how-to/30-migratie-kubeadm.md) | Hard Way → kubeadm op dezelfde hosts (incl. Ansible + build log) |
| [BUILDLOG](../explanation/BUILDLOG.md) | Chronologisch logboek van alle wijzigingen |
| [BUILDLOG-migratie-kubeadm](../explanation/BUILDLOG-migratie-kubeadm.md) | Template build log per fase bij handmatige migratie |

## Status

| Component | Status |
|-----------|--------|
| cp-01 (Control Plane) | ✅ Running |
| node-01 (Worker) | ✅ Running |
| node-02 (Worker) | ✅ Running |
| Kubernetes v1.29.2 | ✅ Installed (the Hard Way) |
| Cilium 1.19.0 | ✅ Installed |
| CoreDNS (kube-dns) | ✅ Cluster DNS |
| Gateway API CRDs | ✅ Installed |
| Cilium Gateway controller | ✅ Actief |
| MetalLB | ⏳ Stap 3 — zie [23-metallb.md](../how-to/23-metallb.md) |
| cert-manager | ⏳ Stap 4 — zie [24-cert-manager.md](../how-to/24-cert-manager.md) |
| Gateway + TLS | ⏳ Stap 5 — zie [25-gateway-tls.md](../how-to/25-gateway-tls.md) |
| Argo CD | ⏳ Pending |
