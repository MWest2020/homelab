---
title: Filosofie
sidebar_position: 1
---

# Filosofie

De principes waarop de homelab rust. Kort, want het zijn vuistregels — niet een verhaal
(dat staat op [westerweel.work](https://westerweel.work)).

## Virtualiseer het fundament

De basis is een [Proxmox](https://www.proxmox.com/)-cluster, geen baremetal. Virtualisatie
ontkoppelt hardware van workload: snapshots vóór een wijziging, herbouw zonder risico, en
— met meerdere fysieke hosts — échte hardware-HA. Kubernetes draait als VM's daarop, niet
op het ijzer.

## HA betekent oneven quorum

Zowel corosync (Proxmox) als etcd (Kubernetes) willen een **oneven** aantal stemmen. Drie
nodes = er mag er één uitvallen. **Twee is slechter dan één**: elke uitval breekt de
meerderheid. Daarom 3 control-plane-nodes, verdeeld over 3 fysieke machines (anti-affinity).

## Alles als code

Geen handmatige klikken in een UI als het via code kan:

- **Terraform** provisioned de VM's (Proxmox-API).
- **Ansible** configureert ze (OS, kubeadm, addons).
- **Argo CD** reconcilieert de clusterstaat vanuit Git.

Git is de bron van waarheid; de werkelijkheid volgt.

## Boring, auditable, solid

Battle-tested boven clever. Optimaliseer voor lees- en controleerbaarheid, niet voor
elegantie. De maatstaf: kan een ander (of een auditor) dit volgen **zonder de context die
in mijn hoofd zit**? Zo niet, dan is het nog niet af.

## Scheiding van zorgen

De hypervisor weet niets van wat er in de VM's draait — je kunt de Kubernetes-laag weggooien
en vervangen zonder het Proxmox-cluster aan te raken. En documentatie over een cluster hoort
níét op dat cluster: ligt het plat, dan wil je de [runbooks](../runbooks/) juist kunnen lezen.
