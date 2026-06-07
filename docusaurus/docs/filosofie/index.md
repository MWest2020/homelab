---
title: Filosofie
sidebar_position: 1
---

# Filosofie

Waarom de homelab is zoals 'ie is.

- **Proxmox-clusters als fundament** — virtualisatie ontkoppelt hardware van workload:
  snapshots, herbouw, VM-flexibiliteit, en HA over meerdere fysieke machines.
- **HA met oneven quorum** — zowel corosync (Proxmox) als etcd (Kubernetes) willen een
  oneven aantal stemmen. 3 nodes = 1 mag uitvallen; 2 is slechter dan 1.
- **IaC + GitOps** — Terraform provisioned, Ansible configureert, Argo CD reconcilieert.
  Git is de bron van waarheid.
- **Boring, auditable, solid** — battle-tested boven clever. Een toekomstige beheerder
  (of auditor) moet het zonder context kunnen volgen.

*(Stub — wordt uitgebreid; de freshness-agent distilleert hier de OpenSpec-rationale in.)*
