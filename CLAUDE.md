# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

```
homelab/
├── ansible/                 # IaC — node provisioning and k8s bootstrap
│   ├── ansible.cfg          # Default inventory, become=sudo, no host-key checking
│   ├── group_vars/k8s_cluster.yml  # Cluster variables (k8s version, CIDRs, APT repo)
│   ├── inventory/hosts.yml  # Git-ignored; copy from hosts.yml.example
│   └── playbooks/           # Ordered playbooks (see Ansible section below)
├── cluster-config/infra/cilium/values.yaml  # Helm values for Cilium (example checked in)
├── kubernetes/infrastructure/   # Raw manifests: cert-manager, coredns, gateway, metallb
├── docs/                    # Detailed documentation in Dutch (Markdown)
└── scripts/                 # Placeholder for future utility scripts
```

## Network topology

| Network | Range | Details |
|---------|-------|---------|
| LAN | 192.168.178.0/24 | cp-01 (.201), node-01 (.202), node-02 (.203) |
| Pod CIDR | 10.200.0.0/16 | /24 per node |
| Service CIDR | 10.32.0.0/24 | CoreDNS at 10.32.0.10 |
| MetalLB pool | 192.168.178.220–230 | Outside DHCP range (reserved) |

## Ansible playbooks (run order for fresh cluster)

All commands run from `ansible/`:

```bash
# 1. Prepare OS-level prerequisites on all nodes
ansible-playbook -i inventory/hosts.yml playbooks/prepare-nodes.yml

# 2. Install kubeadm/kubelet/kubectl packages
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-install-packages.yml

# 3. (If rebuilding) Clean previous cluster state
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-cleanup-before-bootstrap.yml

# 4. Bootstrap control plane + join workers
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-bootstrap.yml

# 5. Post-bootstrap (kubeconfig, addons)
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-post-bootstrap.yml

# Miscellaneous
ansible-playbook -i inventory/hosts.yml playbooks/deploy-ssh-keys.yml
ansible-playbook -i inventory/hosts.yml playbooks/configure-passwordless-sudo.yml
```

## Cilium upgrade

```bash
helm upgrade cilium cilium/cilium -n kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

Key Cilium settings: `kubeProxyReplacement=true`, Hubble observability enabled, Gateway API enabled.

## GitOps roadmap (current progress)

The 7-step plan towards a fully GitOps-managed cluster (`docs/20-stappenplan-gitops.md`):

| Step | Status | Component |
|------|--------|-----------|
| 1 | ✅ | Gateway API CRDs |
| 2 | ✅ | Cilium Gateway (GatewayClass active) |
| 3 | ✅ | MetalLB — L2 mode, pool 192.168.178.220–230 |
| 4 | ✅ | cert-manager + Cloudflare DNS-01 wildcard (`*.westerweel.work`) |
| 5 | ✅ | Gateway + TLS termination |
| 6 | ✅ | Argo CD — `argocd.westerweel.work` |
| 7 | ⏳ | GitOps root app (app-of-apps pattern) |

Once Argo CD is running, all changes go through Git — `kubectl apply` directly to production is only a bootstrap step, not ongoing practice.

## Proxmox VM deployment pipeline

All VM provisioning and configuration follows this pipeline — no manual SCP, no ad-hoc SSH commands in production.

```
Git repo (source of truth)
  ├─ Terraform → provisions VMs on Proxmox/cloud provider
  ├─ Ansible  → configures VMs (Docker, compose files, secrets)
  └─ CI/CD    → triggers Ansible on push to main
```

### Layers

| Layer | Tool | What it does |
|-------|------|-------------|
| Infrastructure | Terraform | Create/destroy VMs (Proxmox API, CYSO API) |
| Configuration | Ansible | Install Docker, deploy compose files, manage secrets |
| Application | Docker Compose | Run Nextcloud, Nginx, MariaDB, Valkey per tenant |
| Routing | Caddy (proxy VM) | TLS termination, hostname-based routing to tenant VMs |
| Secrets | Ansible Vault | Encrypted in git, decrypted at deploy time |

### VM layout (Proxmox laptop node)

| VM ID | Name | IP | Role |
|-------|------|-----|------|
| 100 | proxy | 192.168.178.50 | Caddy reverse proxy |
| 101 | klant-a | 192.168.178.51 | Nextcloud tenant |
| 102 | klant-b | 192.168.178.52 | Nextcloud tenant |
| 103 | klant-c | 192.168.178.53 | Nextcloud tenant |
| 104 | portainer | 192.168.178.54 | Container management UI |
| 9000 | ubuntu-24.04-template | - | Cloud image template (frozen) |

### Directory structure

```
docker/
├── nextcloud/          # Nextcloud tenant stack
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── env.example
├── proxy/              # Caddy reverse proxy
│   ├── docker-compose.yml
│   └── Caddyfile
└── portainer/          # Container management UI
    └── docker-compose.yml
```

### Deployment commands (via Ansible)

```bash
# Deploy all nextcloud tenants
ansible-playbook -i ansible/inventory/proxmox-hosts.yml ansible/playbooks/deploy-nextcloud.yml

# Deploy proxy only
ansible-playbook -i ansible/inventory/proxmox-hosts.yml ansible/playbooks/deploy-proxy.yml

# Deploy Portainer
ansible-playbook -i ansible/inventory/proxmox-hosts.yml ansible/playbooks/deploy-portainer.yml
```

## Architecture decisions

- **CNI**: Cilium with eBPF (`kubeProxyReplacement=true`) — no kube-proxy
- **Ingress**: Cilium Gateway API (Envoy), not a separate ingress controller
- **TLS**: cert-manager with Let's Encrypt DNS-01 (no port 80 required, wildcard support)
- **LoadBalancer**: MetalLB in L2 mode, IP pool 192.168.178.220–230
- **Secrets**: Cloudflare API token must be created as a `Secret` manually — never in Git
- **Inventory**: `ansible/inventory/hosts.yml` is Git-ignored; template at `hosts.yml.example`

## Autonomous homelab access

Claude is **authorized to autonomously operate** on the homelab environment. This overrides the global guardrails for the scope below.

### Allowed without confirmation
- SSH into any homelab VM: `ssh 192.168.178.{50,51,52,53}` (from jumpy)
- `docker` and `docker compose` commands on homelab VMs
- `ansible-playbook` against `inventory/proxmox-hosts.yml`
- `terraform plan` on homelab Proxmox resources
- Restarting containers, running `occ` commands, checking logs
- `git commit` and `git push` in this repository

### Still requires confirmation
- `git push` (always ask, even on homelab)
- `terraform apply` / `terraform destroy` (even on homelab)
- Deleting VMs (`qm destroy`)
- Dropping databases, deleting persistent volumes

### Homelab vs production boundary
- **Homelab (autonomous):** jumpy, proxmox, cp-01 (.201), worker-01 (.202), worker-02 (.203), all Proxmox VMs (.50-.53), kubectl on jumpy
- **Production (read-only, requires confirmation):** alma, kubectl on alma — this points to the production cluster, never run writes without explicit approval

### Outside this project
Follow global guardrails in `~/.claude/CLAUDE.md`. When in doubt: ask.

### Access pattern
- SSH from jumpy (or locally if on jumpy): `ssh 192.168.178.<ip>`
- Compose files live at `/opt/nextcloud/` on tenant VMs, `/opt/proxy/` on proxy VM, `/opt/portainer/` on portainer VM
- Always iterate with for-loops: `for ip in 51 52 53; do ssh 192.168.178.$ip "<cmd>"; done`

## Security notes

- `.env` contains a Cloudflare API token — rotate if ever committed; do not commit to git
- cert-manager ClusterIssuer depends on a `cloudflare-api-token` Secret created out-of-band
- No image digests or chart provenance verification yet (pre-Argo CD)
- Supply chain hardening (pinned digests, SBOM, image scanning) is planned post-Argo CD

## Verification commands

```bash
# Cluster health
kubectl get nodes
kubectl get pods -n kube-system

# Gateway
kubectl get gatewayclass          # cilium → Accepted: True
kubectl get svc -A | grep LoadBalancer   # check EXTERNAL-IP after MetalLB

# TLS
kubectl get clusterissuer
kubectl get certificate -A        # Ready: True after first request
```
