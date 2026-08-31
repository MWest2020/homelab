---
title: Archief
sidebar_position: 1
---

# Archief

Historie — bewaard, niet weggegooid. Hoe de homelab eruitzag vóór het Proxmox-cluster.

## Baremetal "Kubernetes the Hard Way"

De eerste opzet draaide Kubernetes **direct op baremetal**, handmatig opgezet volgens
[Kubernetes the Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way) —
bewust gekozen voor maximaal begrip van de losse onderdelen (systemd-units, certs,
etcd, kubelet) i.p.v. een kant-en-klare installer.

- **Hardware:** 3× HP EliteDesk Mini-PC's.
- **Topologie:** één control-plane + twee workers, direct op de fysieke machines —
  cp-01 (`192.168.178.201`), node-01 (`192.168.178.202`), node-02 (`192.168.178.203`).
- **Versies:** Kubernetes v1.29.2, Cilium 1.19.0, CoreDNS als cluster-DNS.
- Eén control-plane, dus **geen HA**: uitval van die node legde de API-server plat.

## Migratie: Hard Way → kubeadm

Het handmatige cluster is vervangen door een **kubeadm**-cluster op dezelfde hosts —
geen twee clusters naast elkaar (één kubelet per node), dus een vervanging met korte
downtime. De jumpbox, hostnamen en IP's bleven gelijk; alleen de clusterinhoud werd
opnieuw opgezet. Dit bracht de provisioning onder Ansible (`prepare-nodes` →
`kubeadm-install-packages` → `kubeadm-bootstrap` → `kubeadm-post-bootstrap`) in plaats
van de handmatige systemd-stappen.

## Naar het Proxmox-VM-cluster

Daarna is de homelab verhuisd van baremetal naar het huidige **3-node Proxmox-cluster
met HA-Kubernetes op VM's** (3 control-plane + 3 workers, kube-vip VIP `.201`). Daarmee
verdween het single-control-plane-model: virtualisatie ontkoppelt hardware van workload
en maakt anti-affinity over 3 fysieke machines mogelijk. De huidige staat staat onder
[Architectuur](../architectuur/).

## MinIO als S3-store (maart – augustus 2026)

Het cluster draaide **MinIO** als S3-compatibele object storage (Helm-deploy, 50Gi PVC,
namespace `minio`) — in maart 2026 neergezet voor een geplande Nextcloud-deploy, en
vanaf augustus 2026 pragmatisch ook het S3-endpoint van de Wordsworth-straat. De
buzz-relay-VM draaide daarnaast een eigen MinIO in z'n compose-stack.

MinIO's open-source-editie werd echter gearchiveerd (2026-04-25, geen security-updates
meer). Op **2026-08-27** is alles naar SeaweedFS gemigreerd en is MinIO overal
verwijderd — wordsworth-data checksum-geverifieerd overgezet (414 objecten), de
nextcloud-bucket bleek leeg, buzz-relay's media idem gemigreerd (21 objecten). De
afwegingen staan onder [Beslissingen](../beslissingen/); de uitvoering in de
gearchiveerde OpenSpec-changes van 2026-08-27 in de repo.

## Nextcloud-tenants op Docker (laptop-node)

Naast het K8s-cluster draaien Nextcloud-tenants als Docker-compose-stacks op VM's op de
laptop-Proxmox-node, met een Caddy-proxy ervoor (hostname-routing + TLS). Dit is geen
historie maar een parallel spoor; het staat hier genoteerd omdat het buiten het
K8s-cluster valt.
