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

## GitOps: apps beheren (Argo CD app-of-apps)

Eén root-Application beheert alle child-apps onder `apps/infrastructure/`. De root wordt
éénmalig gebootstrapt; daarna gaat **alles via Git** — geen `kubectl apply` naar productie.

```bash
# Eenmalige bootstrap (daarna beheert Argo CD zichzelf)
kubectl apply -f apps/root-app.yaml

# Nieuwe app toevoegen = YAML in apps/infrastructure/ committen; de root pikt 'm op
kubectl get applications -n argocd          # sync-status van alle apps
```

Sync-waves bepalen de volgorde (operator-CRDs vóór de CRs die ze nodig hebben). Operators
met te grote CRDs (CNPG, Tailscale) syncen met `ServerSideApply=true` — client-side apply
loopt daar stuk op de 256KB-annotation-limiet.

## Wordsworth-straat: deployen & verifiëren

De RAG-stack (zie [Architectuur](../architectuur/)) is volledig GitOps. Een nieuwe
API-versie uitrollen = de commit-SHA-tag pinnen in
`cluster-config/infra/wordsworth/api.yaml` **én** `init-job.yaml`, committen — Argo CD
synct de rest (PreSync init-Job draait eerst, idempotent, voor het DB-schema).

Prerequisite-secrets (out-of-band, nooit in Git): `wordsworth-db` en `wordsworth-s3`
(namespace `wordsworth`), `minio-credentials` (namespace `minio`), `operator-oauth`
(namespace `tailscale`).

```bash
# Status van de hele straat
kubectl get applications -n argocd | grep -E 'wordsworth|ollama|opensearch|openanonymiser|cnpg|minio'
kubectl -n wordsworth get pods
kubectl -n cnpg-database get cluster homelab-pg   # 3 instances, Cluster in healthy state

# API-health (in-cluster of via de tailnet-hostname)
kubectl -n wordsworth port-forward svc/wordsworth-api 8000:8000 &
curl -s localhost:8000/health
```

Extra Ollama-model nodig? Toevoegen aan de PostSync-pull-Job
(`cluster-config/infra/ollama/pull-bge-m3.yaml`) en committen — de hook draait bij de
volgende sync opnieuw. Let op: CPU-only, een pull + cold-start duurt minuten.

:::note Geheugen-tuning ingest
`/ingest` buffert PDF-uploads in het API-proces. De limit staat op 4Gi en gunicorn
recyclet workers via `--max-requests`; grote corpora gaan batch-gewijs, niet in één call.
:::

## Applicaties deployen (Proxmox-VM's)

De Nextcloud-tenants, proxy en Portainer draaien als Docker-compose-stacks op de
laptop-Proxmox-VM's. Deploy via Ansible:

```bash
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-nextcloud.yml
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-proxy.yml
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-portainer.yml
```

## CrowdSec uitrollen (edge-detectie + blocking op de proxy)

CrowdSec draait naast Caddy op de proxy-VM (`192.168.178.50`): de engine parst Caddy's
JSON-access-log en genereert alerts/decisions, en sinds fase A.2 dwingt een **Caddy-L7-
bouncer** die decisions af — een gebande IP krijgt een 403. Achtergrond: zie
[Beslissingen](../beslissingen/).

Prerequisite: Caddy schrijft zijn access-log naar de gedeelde host-bind-mount
`/var/log/caddy/access.log` (de `(secured)`-snippet in de Caddyfile). De volgorde is
**crowdsec eerst, dan de proxy** — `deploy-crowdsec-proxy.yml` zet de LAPI, het
`crowdsec-lapi`-netwerk en de bouncer-key (`/opt/proxy/.env`) klaar die de proxy-stack
nodig heeft bij start:

```bash
# 1. Engine + crowdsec-lapi-net + bouncer registreren (schrijft /opt/proxy/.env)
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-crowdsec-proxy.yml

# 2. Custom Caddy-image (mét bouncer) bouwen + proxy omwisselen
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-proxy.yml
```

De crowdsec-deploy is **zelf-verifiërend**: hij faalt hard als `cscli lapi status` niet
binnen ~1 min gezond opkomt (collections + LAPI-startup duren even) en print daarna
`cscli metrics`.

Inspecteren:

```bash
ssh 192.168.178.50 'docker exec crowdsec cscli bouncers list'   # caddy-bouncer → Valid
ssh 192.168.178.50 'docker exec crowdsec cscli metrics'
ssh 192.168.178.50 'docker exec crowdsec cscli alerts list'
ssh 192.168.178.50 'docker exec crowdsec cscli decisions list'  # actieve bans
```

### IP bannen / unbannen (handmatig)

De bouncer pullt nieuwe decisions elke 15s (`ticker_interval`), dus een ban/unban wordt na
~15s actief op de proxy.

```bash
# Bannen (tijdelijk — altijd een duur meegeven)
ssh 192.168.178.50 'docker exec crowdsec cscli decisions add --ip 203.0.113.7 --duration 4h --reason "handmatig"'

# Unbannen
ssh 192.168.178.50 'docker exec crowdsec cscli decisions delete --ip 203.0.113.7'
```

Enforcement testen zonder echte aanvaller: ban een IP, doe een request en verwacht **403**;
verwijder de decision en verwacht weer een normale respons (302).

:::warning Client-IP vóór go-live
Achter de Docker-`userland-proxy` ziet Caddy nu de bridge-gateway (`172.20.0.1`, RFC1918)
i.p.v. de echte client. CrowdSec whitelist RFC1918 standaard → bij écht publiek verkeer
worden aanvallen weggewhitelist. Fix vóór de proxy scherp publiek gaat: `trusted_proxies`
+ XFF in de Caddyfile, of `userland-proxy: false` op de daemon.
:::

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
