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

## Netwerk

| Netwerk | Range | Nodes |
|---------|-------|-------|
| LAN | 192.168.178.0/24 | cp-01 (.201), node-01 (.202), node-02 (.203) |
| Pod CIDR | 10.200.0.0/16 | /24 per node |
| Service CIDR | 10.32.0.0/24 | ClusterIP's |
