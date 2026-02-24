# Kubernetes the Hard Way

We installeren Kubernetes volledig handmatig volgens de [Kelsey Hightower tutorial](https://github.com/kelseyhightower/kubernetes-the-hard-way), aangepast voor onze homelab setup.

## Waarom the Hard Way?

- **Begrip**: Je snapt elk component en waarom het er is
- **Debugging**: Als iets kapot gaat, weet je waar je moet kijken
- **Geen magic**: Geen hidden defaults van K3s/MicroK8s/etc

## Onze Setup vs Tutorial

| Tutorial | Onze Setup |
|----------|------------|
| GCP VMs | HP EliteDesk Mini-PC's |
| 3 controllers + 3 workers | 1 control plane + 2 workers |
| GCP networking | Flat LAN (192.168.178.0/24) |

## Componenten Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTROL PLANE (node01)                  │
├─────────────────────────────────────────────────────────────┤
│  etcd          - Cluster state database                     │
│  kube-apiserver    - API endpoint                           │
│  kube-scheduler    - Pod placement decisions                │
│  kube-controller-manager - Reconciliation loops             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     WORKERS (node02, node03)                │
├─────────────────────────────────────────────────────────────┤
│  kubelet       - Node agent, runs pods                      │
│  kube-proxy    - Network rules for services                 │
│  containerd    - Container runtime                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     NETWORKING                              │
├─────────────────────────────────────────────────────────────┤
│  CNI plugin    - Pod networking (we kiezen later)           │
│  CoreDNS       - Cluster DNS                                │
└─────────────────────────────────────────────────────────────┘
```

## Netwerk Configuratie

```
Node Network:    192.168.178.0/24
Pod CIDR:        10.200.0.0/16
  - node01:      10.200.0.0/24
  - node02:      10.200.1.0/24
  - node03:      10.200.2.0/24
Service CIDR:    10.32.0.0/24
Cluster DNS:     10.32.0.10
```

## Stappenplan

### Dag 1: Certificaten & Configuratie
- [ ] Certificate Authority (CA) aanmaken
- [ ] Client certificaten genereren
- [ ] Kubernetes config files genereren
- [ ] Data encryption config

### Dag 2: etcd Cluster
- [ ] etcd installeren op control plane
- [ ] Cluster bootstrappen
- [ ] Verificatie

### Dag 3: Control Plane
- [ ] kube-apiserver configureren
- [ ] kube-controller-manager configureren  
- [ ] kube-scheduler configureren
- [ ] kubectl configureren voor remote access

### Dag 4: Worker Nodes
- [ ] containerd installeren
- [ ] kubelet configureren
- [ ] kube-proxy configureren

### Dag 5: Networking & DNS
- [ ] CNI plugin installeren
- [ ] Pod routes configureren
- [ ] CoreDNS deployen → manifest: `kubernetes/infrastructure/coredns/coredns.yaml`

### Dag 6: Smoke Tests
- [ ] Pod deployment test
- [ ] Service test
- [ ] DNS test

## Tools Nodig

Op je **lokale machine**:
```bash
# cfssl - Certificate generation
# kubectl - Kubernetes CLI

# We installeren deze wanneer we beginnen
```

## Referenties

- [Kubernetes the Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way)
- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/)
- [PKI Certificates](https://kubernetes.io/docs/setup/best-practices/certificates/)

## Volgende Stap

Zodra de nodes geprepareerd zijn (zie [Post-install](04-post-install.md)), beginnen we met de certificaten.

Gedetailleerde instructies per stap komen in:
- [07-certificates.md](07-certificates.md)
- [08-etcd.md](08-etcd.md)
- [09-control-plane.md](09-control-plane.md)
- [10-workers.md](10-workers.md)
- [11-networking.md](11-networking.md)
