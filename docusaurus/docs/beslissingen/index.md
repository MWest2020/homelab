---
title: Beslissingen
sidebar_position: 1
---

# Beslissingen

De afwegingen achter de architectuur. Hieronder de keuzes die direct uit de repo
(Terraform-modules, Ansible-playbooks, comments) blijken.

## 3 control-plane (HA), nooit 2

etcd en corosync willen een **oneven** quorum. Met 3 control-plane-nodes mag er 1
uitvallen (2/3 quorum blijft) en leeft het cluster door. Met 2 nodes is het quorum
juist slechter dan met 1: elke uitval breekt de meerderheid. Daarom 3 CP-VM's, verdeeld
over 3 fysieke Proxmox-hosts (anti-affinity), met een kube-vip VIP (`192.168.178.201`)
als stabiel control-plane-endpoint.

## Template-per-shape i.p.v. post-clone hardware-overrides

De `k8s-cluster`-Terraform-module bevat **bewust geen** `cpu`/`memory`/`disk`/
`operating_system`-blocks. De bpg Proxmox-provider hangt op post-clone hardware-overrides,
dus de shape komt 100% uit de template. Gevolg: één template per VM-vorm, en de VMID's
zijn cluster-breed uniek (per host een eigen reeks: 9001/9002, 9011/9012, 9021/9022).

## kube-vip VIP als endpoint, niet één CP-adres

De kubeconfig en het control-plane-endpoint wijzen naar de kube-vip VIP
`192.168.178.201`, niet naar een individuele control-plane-node. Zo blijft het cluster
bereikbaar als de node achter een vast adres wegvalt. De VIP zit bewust **niet** in
Terraform (`var.vms`) — die wordt door Ansible/kube-vip beheerd.

## local-lvm i.p.v. gedeelde storage

Storage is `local-lvm` per Proxmox-node. Geen Ceph: dat is binnen homelab-scope te veel
overhead. HA wordt op cluster-niveau (etcd-quorum + anti-affinity over hosts) opgelost,
niet op storage-niveau.

## CrowdSec detection-only first, gedeeld logbestand i.p.v. docker.sock

CrowdSec op de proxy start bewust **detection-only**: de engine parst Caddy's access-log
en genereert alerts, maar er is geen bouncer — niets wordt geblokkeerd. Zo zie je eerst
wat een bouncer zou tegenhouden, vóórdat je het risico op false-positive-blocks op de
publieke surface neemt. De bouncer-keuze (firewall-bouncer vs. Caddy-L7-plugin) en
deelname aan de community-blocklist zijn bewust uitgesteld naar een volgende fase.

De engine leest het access-log via een **gedeelde, read-only host-bind-mount**, niet via
`docker.sock`: een logbestand is auditbaarder en veel minder geprivilegieerd dan
socket-toegang tot de Docker-daemon.

## Docs extern gehost, niet in-cluster

Deze kennisbank (Docusaurus, statische build) wordt **buiten** het cluster gehost, zodat
ze leesbaar blijft als het cluster zelf onbereikbaar is — juist tijdens een incident
wanneer je de runbooks nodig hebt.
