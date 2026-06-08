---
slug: /
title: Homelab
sidebar_position: 1
---

# Homelab

Een 3-node **Proxmox-cluster** met **hoog-beschikbare Kubernetes** op VM's, volledig als
code beheerd (Terraform + Ansible + GitOps). Deze kennisbank legt vast **waarom** het zo
gebouwd is en **hoe** je het draait.

## Wegwijzer

| Sectie | Voor |
|--------|------|
| **[Filosofie](./filosofie/)** | De principes achter de keuzes — het *waarom*. |
| **[Architectuur](./architectuur/)** | De huidige staat — het *wat*. |
| **[Runbooks](./runbooks/)** | Bedienen, bootstrappen, upgraden — het *hoe*. |
| **[Beslissingen](./beslissingen/)** | Concrete afwegingen, kort onderbouwd. |
| **[Archief](./archief/)** | Hoe het was: baremetal → kubeadm → Proxmox. |

Naslag + referentie. Het bredere verhaal en de achtergrond staan op
[westerweel.work](https://westerweel.work).

:::note Scrub-policy
Publieke docs. Bevatten **nooit** Tailscale-IP's (`100.x`), tokens of secrets — alleen
RFC1918-LAN (`192.168.178.x`) en publieke hostnames.
:::
