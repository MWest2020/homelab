---
title: Beslissingen
sidebar_position: 1
---

# Beslissingen

De afwegingen achter de architectuur — afgeleid van de OpenSpec-changes (proposal/design).

Voorbeelden die hier uitgewerkt worden:
- Waarom 3 control-plane (HA) i.p.v. 1, en nooit 2 (etcd-quorum).
- Waarom template-per-shape i.p.v. post-clone hardware-overrides (bpg hangt erop).
- Waarom docs **extern** (Cloudflare Pages) i.p.v. in-cluster (overleeft cluster-uitval).
- Waarom local-lvm i.p.v. Ceph (homelab-scope).

*(Stub — de freshness-agent distilleert afgeronde OpenSpec-changes hierheen.)*
