# Homelab

<div align="center">

![Nextcloud](https://img.shields.io/badge/Nextcloud-0082C9?style=for-the-badge&logo=nextcloud&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![ArgoCD](https://img.shields.io/badge/Argo%20CD-EF7B4D?style=for-the-badge&logo=argo&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-0F1689?style=for-the-badge&logo=helm&logoColor=white)

Infrastructure as Code voor mijn homelab cluster.

## Hardware

- 3x HP EliteDesk Mini-PC (32GB RAM each)
- Ubuntu Server 24.04 LTS
- Kubernetes (the Hard Way)

## Documentatie

Alle documentatie staat in [`/docs`](docs/):

| Document | Beschrijving |
|----------|--------------|
| [Overview](docs/00-overview.md) | Project overzicht en status |
| [Hardware](docs/01-hardware.md) | Hardware specificaties |
| [Network](docs/02-network.md) | Netwerk configuratie en IP schema |
| [Installation](docs/03-installation.md) | Ubuntu Server installatie guide |
| [Post-install](docs/04-post-install.md) | Hardening en setup na installatie |

## Quick Start

### 1. Clone en setup

```bash
git clone <repo-url>
cd Homelab
```

### 2. Maak Ansible inventory

```bash
cp ansible/inventory/hosts.yml.example ansible/inventory/hosts.yml
# Edit hosts.yml als je andere IP's hebt
```

### 3. Gebruik

```bash
# Ansible: prepare nodes
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/prepare-nodes.yml

# Helm: upgrade Cilium
helm upgrade cilium cilium/cilium -n kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

## GitOps Journey

We bouwen stap-voor-stap naar een GitOps-beheerde omgeving:

1. Gateway API CRDs
2. Cilium Gateway enablen
3. MetalLB (LoadBalancer IPs)
4. cert-manager (TLS)
5. Gateway + HTTPS
6. Argo CD
7. App-of-apps

- Plan: [docs/20-stappenplan-gitops.md](docs/20-stappenplan-gitops.md)
- Stap 2 (Cilium Gateway): [docs/22-cilium-gateway.md](docs/22-cilium-gateway.md).
- Stap 3 (MetalLB): [docs/23-metallb.md](docs/23-metallb.md).

## Repository Structuur

```
.
├── docs/                    # Documentatie (chapters)
├── ansible/                 # Ansible configuratie
│   ├── inventory/           # Host definities (.example in Git)
│   ├── playbooks/           # Playbooks
│   └── roles/               # Herbruikbare roles
├── cluster-config/          # GitOps configuratie
│   └── infra/               # Infrastructure components
│       └── cilium/          # CNI + Gateway (values.yaml.example in Git)
├── kubernetes/              # K8s manifests (komt later)
└── scripts/                 # Utility scripts
```

## Netwerk

| Netwerk | Range | Nodes |
|---------|-------|-------|
| LAN | 192.168.178.0/24 | cp-01 (.201), node-01 (.202), node-02 (.203) |
| Pod CIDR | 10.200.0.0/16 | /24 per node |
| Service CIDR | 10.32.0.0/24 | ClusterIP's |

## Status

| Component | Status |
|-----------|--------|
| Kubernetes v1.29.2 | ✅ Running |
| Cilium 1.19.0 | ✅ Running |
| Gateway API CRDs | ✅ Installed |
| Cilium Gateway | ✅ Running |
| MetalLB | ⏳ Pending |
| cert-manager | ⏳ Pending |
| Argo CD | ⏳ Pending |

## License

Private - personal homelab configuration
