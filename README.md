# Homelab

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

```bash
# Clone repo
git clone <repo-url>
cd Homelab

# Setup local config (not in Git)
cp .env.example .env
cp ansible/inventory/hosts.yml.example ansible/inventory/hosts.yml

# Edit files with your IP addresses
# Then run Ansible
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/prepare-nodes.yml
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

Zie [docs/20-stappenplan-gitops.md](docs/20-stappenplan-gitops.md) voor details.

## Repository Structuur

```
.
├── docs/               # Documentatie (chapters)
├── ansible/            # Ansible configuratie
│   ├── inventory/      # Host definities
│   ├── playbooks/      # Playbooks
│   └── roles/          # Herbruikbare roles
├── kubernetes/         # K8s manifests
│   ├── apps/           # Applicaties
│   └── infrastructure/ # Cluster infra
└── scripts/            # Utility scripts
```

## Status

🔄 **In Progress**: Nodes worden geïnstalleerd

## License

Private - personal homelab configuration
