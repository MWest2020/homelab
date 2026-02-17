# Cluster Config

Deze directory bevat de declaratieve configuratie voor het Kubernetes cluster.

## Status

| Fase | Beschrijving |
|------|--------------|
| **Nu** | Configs worden handmatig toegepast via `helm upgrade` |
| **Na Stap 6** | Argo CD neemt beheer over (GitOps) |

## Structuur

```
cluster-config/
├── infra/                    # Infrastructure components
│   ├── cilium/              # CNI + Gateway controller
│   ├── metallb/             # LoadBalancer (komt later)
│   ├── cert-manager/        # TLS certificates (komt later)
│   └── argocd/              # Argo CD zelf (komt later)
└── apps/                     # Application workloads (komt later)
```

## Workflow

### Fase 1: Handmatig (nu)

```bash
# Cilium upgrade met onze values
helm upgrade cilium cilium/cilium \
  -n kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

### Fase 2: GitOps (na Argo CD bootstrap)

Argo CD Applications wijzen naar deze directory. Wijzigingen:
1. Edit YAML in Git
2. Commit + push
3. Argo CD synct automatisch

## Let op

- `values.yaml` bestanden staan in `.gitignore` (bevatten IP's)
- Alleen `values.yaml.example` wordt gecommit
- Na clone: `cp values.yaml.example values.yaml` en vul je IP's in

## Netwerk Conventies

| Netwerk | Range | Gebruik |
|---------|-------|---------|
| LAN | 192.168.xxx.0/24 | Node IP's |
| Pod CIDR | 10.200.0.0/16 | Pod IP's |
| Service CIDR | 10.32.0.0/24 | ClusterIP's |
