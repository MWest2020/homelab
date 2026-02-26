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
| [03 - Installation](03-installation.md) | Ubuntu Server installatie |
| [04 - Post-install](04-post-install.md) | Hardening, prepare nodes |
| [05 - Ansible](05-ansible.md) | Ansible setup en playbooks |
| [06 - Kubernetes](06-kubernetes.md) | Kubernetes the Hard Way |

## GitOps Journey

| Doc | Beschrijving |
|-----|--------------|
| [20 - Stappenplan](20-stappenplan-gitops.md) | Master plan: CRDs → Gateway → Argo CD |
| [21 - Gateway API CRDs](21-gateway-api-crds.md) | CRDs voor Gateway API |
| [22 - Cilium Gateway](22-cilium-gateway.md) | Stap 2: commando's en checks |
| [23 - MetalLB](23-metallb.md) | Stap 3: LoadBalancer IP's |
| [24 - cert-manager](24-cert-manager.md) | Stap 4: TLS (Let's Encrypt, DNS-01) |
| [25 - Gateway TLS](25-gateway-tls.md) | Stap 5: HTTPS Gateway + test |
| [BUILDLOG](BUILDLOG.md) | Chronologisch logboek van alle wijzigingen |

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
| MetalLB | ⏳ Stap 3 — zie [23-metallb.md](23-metallb.md) |
| cert-manager | ⏳ Stap 4 — zie [24-cert-manager.md](24-cert-manager.md) |
| Gateway + TLS | ⏳ Stap 5 — zie [25-gateway-tls.md](25-gateway-tls.md) |
| Argo CD | ⏳ Pending |
