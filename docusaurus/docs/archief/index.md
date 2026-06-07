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

## Nextcloud-tenants op Docker (laptop-node)

Naast het K8s-cluster draaien Nextcloud-tenants als Docker-compose-stacks op VM's op de
laptop-Proxmox-node, met een Caddy-proxy ervoor (hostname-routing + TLS). Dit is geen
historie maar een parallel spoor; het staat hier genoteerd omdat het buiten het
K8s-cluster valt.
