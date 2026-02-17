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
| [BUILDLOG](BUILDLOG.md) | Chronologisch logboek van alle wijzigingen |

## Status

| Component | Status |
|-----------|--------|
| cp-01 (Control Plane) | ✅ Running |
| node-01 (Worker) | ✅ Running |
| node-02 (Worker) | ✅ Running |
| Kubernetes v1.29.2 | ✅ Installed (the Hard Way) |
| Cilium 1.17.0 | ✅ Installed |
| Argo CD | 🔄 Setup in progress |
| Gateway API | 🔄 Setup in progress |
