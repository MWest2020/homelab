---
title: Runbooks
sidebar_position: 1
---

# Runbooks

Operationele how-to's, afgeleid van de Ansible-playbooks en Terraform-modules in de repo.

:::info Vanaf jumpy
Alle homelab-commando's draaien vanaf **jumpy** — niet vanaf alma (alma's `kubectl`
wijst naar productie). Ansible-commando's draaien vanuit `ansible/`, Terraform vanuit
de betreffende module onder `terraform/`.
:::

## VM's provisionen (Terraform)

De Kubernetes-VM's (3 control-plane + 3 workers) worden data-driven aangemaakt door
per-shape templates te clonen. De shape (cpu/mem/disk) komt 100% uit de template — er
zijn bewust geen post-clone hardware-overrides (zie [Beslissingen](../beslissingen/)).

```bash
cd terraform/k8s-cluster
terraform plan
terraform apply   # vereist bevestiging
```

Kubernetes zelf wordt niet door Terraform geconfigureerd, maar door de Ansible-playbooks
hieronder.

## Templates bouwen

Bouwt de K8s-VM-templates op de Proxmox-hosts. VMID's zijn cluster-breed uniek, dus elke
host heeft zijn eigen reeks (px-01 → 9001/9002, px-02 → 9011/9012, px-03 → 9021/9022).

```bash
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/build-k8s-templates.yml
```

## K8s greenfield bootstrap

Volgorde voor een vers HA-cluster (vanuit `ansible/`):

```bash
# 1. OS-prerequisites op alle nodes (incl. containerd)
ansible-playbook -i inventory/hosts.yml playbooks/prepare-nodes.yml

# 2. kubeadm/kubelet/kubectl installeren
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-install-packages.yml

# 3. (alleen bij herbouw) vorige clusterstaat opruimen
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-cleanup-before-bootstrap.yml

# 4. HA control-plane bootstrappen (kube-vip VIP .201) + workers joinen
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-bootstrap.yml

# 5. Post-bootstrap: kubeconfig ophalen + addons
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-post-bootstrap.yml
```

De kubeconfig blijft naar de kube-vip VIP `192.168.178.201:6443` wijzen — dat overleeft
het uitvallen van een control-plane-node.

## Node-onderhoud & upgrades

Housekeeping (journald-cap + wekelijkse cleanup-timer, **geen** upgrades):

```bash
ansible-playbook -i inventory/hosts.yml playbooks/node-maintenance.yml
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/node-maintenance.yml
```

Package-updates, drain-aware, één node tegelijk (draai uitsluitend vanaf jumpy — gebruikt
`kubectl` via `delegate_to: localhost`):

```bash
# K8s-nodes: drain → upgrade → reboot → uncordon
ansible-playbook -i inventory/hosts.yml playbooks/node-update.yml

# VM's: upgrade → reboot
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/node-update.yml
```

`node-update.yml` houdt kubelet/kubeadm/kubectl op `apt-mark hold`. Een cluster-versie-hop
is een aparte operatie via `playbooks/kubeadm-upgrade.yml`.

## Cilium upgraden

```bash
helm upgrade cilium cilium/cilium -n kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

Kerninstellingen: `kubeProxyReplacement=true`, Hubble aan, Gateway API aan.

## Applicaties deployen (Proxmox-VM's)

De Nextcloud-tenants, proxy en Portainer draaien als Docker-compose-stacks op de
laptop-Proxmox-VM's. Deploy via Ansible:

```bash
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-nextcloud.yml
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-proxy.yml
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-portainer.yml
```

## CrowdSec uitrollen (proxy, detection-only)

CrowdSec draait als losse engine naast Caddy op de proxy-VM (`192.168.178.50`). Het
parst Caddy's JSON-access-log en genereert alerts/decisions — er is **(nog) geen
bouncer**, dus er wordt niets geblokkeerd (zie [Beslissingen](../beslissingen/)).

```bash
# 1. Caddy mét access-logging herdeployen (prerequisite — schrijft /var/log/caddy)
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-proxy.yml

# 2. CrowdSec-engine erbij
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-crowdsec-proxy.yml
```

De deploy is **zelf-verifiërend**: hij faalt hard als de local API niet gezond opkomt
(`cscli lapi status`, 12×5s retry) en print daarna `cscli metrics`. Handmatig inspecteren:

```bash
ssh 192.168.178.50 'docker exec crowdsec cscli metrics'     # parser/acquisition
ssh 192.168.178.50 'docker exec crowdsec cscli alerts list' # gedetecteerd (geen blocks)
```

## Graceful shutdown (stroomonderbreking)

`scripts/graceful-shutdown.sh` sluit de hele homelab netjes af vóór een geplande
stroomonderbreking. Draait vanaf **jumpy** (die blijft up): per Proxmox-host alle VM's/CT's
gracefully afsluiten → host halten → pollen tot alles down is → sein *"stroom kan eraf"*.

```bash
./scripts/graceful-shutdown.sh
```

Power-up daarna is handmatig (hosts aanzetten); K8s-VM's met `onboot=1` starten vanzelf.
Verifieer met `pvecm status` (3 quorate) en `kubectl get nodes` (6 Ready).
