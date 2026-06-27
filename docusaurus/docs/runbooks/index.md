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

## CrowdSec uitrollen (edge-detectie op de proxy)

CrowdSec draait **detection-only** naast Caddy op de proxy-VM (`192.168.178.50`): de
engine parst Caddy's JSON-access-log en genereert alerts/decisions, maar er is (nog) geen
bouncer — er wordt niets geblokkeerd. Achtergrond: zie [Beslissingen](../beslissingen/).

Prerequisite: Caddy moet zijn access-log schrijven naar de gedeelde host-bind-mount
`/var/log/caddy/access.log` (de `(accesslog)`-snippet in de Caddyfile). Draai daarom eerst
`deploy-proxy.yml`:

```bash
# 1. Caddy mét access-logging (prerequisite — schrijft /var/log/caddy/access.log)
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-proxy.yml

# 2. CrowdSec-engine ernaast
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-crowdsec-proxy.yml
```

De deploy is **zelf-verifiërend**: hij faalt hard als `cscli lapi status` niet binnen
~1 min gezond opkomt (collections + LAPI-startup duren even) en print daarna `cscli metrics`.

Inspecteren (detection-only — alerts, geen blocks):

```bash
ssh 192.168.178.50 'docker exec crowdsec cscli metrics'
ssh 192.168.178.50 'docker exec crowdsec cscli alerts list'
```

## Homelab gracefully afsluiten (stroomonderbreking)

`scripts/graceful-shutdown.sh` draait vanaf **jumpy** (die blijft up) en zet de hele
homelab netjes uit voor een geplande stroomonderbreking: per Proxmox-host worden alle
draaiende VM's en containers gracefully afgesloten (ACPI), daarna halt de host. Het script
pollt tot alles down is en geeft het sein "stroom kan eraf".

```bash
./scripts/graceful-shutdown.sh
```

Power-up daarna (handmatig): hosts weer aanzetten — de K8s-VM's (`onboot=1`) starten
vanzelf. Verifieer:

```bash
pvecm status        # 3 nodes quorate
kubectl get nodes   # 6× Ready (vanaf jumpy)
```
