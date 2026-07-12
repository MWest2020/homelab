---
status: draft
last_reviewed: 2026-07-12
---

# Homelab docs

Documentatie voor de homelab: een 3-node Proxmox-cluster met een via kubeadm
gebootstrapte Kubernetes-cluster (Cilium, Gateway API, MetalLB, cert-manager,
Argo CD) plus een Proxmox-VM-stack voor Nextcloud-tenants. Status: in gebruik,
GitOps-migratie loopt (zie stappenplan). Zie de [README](../README.md) voor de
snelle projectkaart; deze `docs/` bevat de uitgewerkte documentatie.

> **Niet in de publieke handbook-import.** Deze docs horen bij de private
> handbook-sectie (Westmarch change 2, taak 3.1) en worden **niet** meegenomen
> in de publieke handbook-aggregatie.

## Secties

- **[reference/](reference/00-overview.md)** — feiten: overzicht, hardware, netwerk/IP-schema.
- **[how-to/](how-to/03-installation.md)** — taakgericht: installatie, Ansible, Kubernetes, VM-provisioning, GitOps-stappen, migratie, [GPU CUDA-reset](how-to/gpu-cuda-reset.md).
- **[explanation/](explanation/BUILDLOG.md)** — waarom/achtergrond: build logs van de GitOps-reis en de kubeadm-migratie.
