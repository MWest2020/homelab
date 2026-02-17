# Build Log - Homelab GitOps Journey

Dit logboek documenteert elke stap in het opzetten van GitOps voor onze Kubernetes the Hard Way cluster.

**Stappenplan:** Zie [20-stappenplan-gitops.md](20-stappenplan-gitops.md)

## Cluster Context

| Component | Waarde |
|-----------|--------|
| Kubernetes | v1.29.2 (the Hard Way, systemd) |
| Runtime | containerd |
| CNI | Cilium 1.19.0 (kubeProxyReplacement=true) |
| Control Plane | cp-01 |
| Workers | node-01, node-02 |
| Pod CIDR | 10.200.0.0/16 |
| Service CIDR | 10.32.0.0/24 |
| Domein | westerweel.work (wildcard) |

---

## Log Entries

### 2026-02-12 21:45 (Amsterdam) - Setup

**Actie:** Repository structuur opgezet voor stap-voor-stap GitOps journey.

**Bestanden:**
- `docs/20-stappenplan-gitops.md` - Master stappenplan
- `docs/BUILDLOG.md` - Dit logboek

**Opgeschoond:**
- `cluster-config/` directory verwijderd (te vroeg gegenereerd)
- `docs/12-gitops.md` verwijderd

---

### 2026-02-17 20:16 (Amsterdam) - Stap 1: Gateway API CRDs

**Actie:** Gateway API CRDs v1.2.0 geïnstalleerd (standard channel).

**Commando's uitgevoerd (jumpbox):**
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_gatewayclasses.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_gateways.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_httproutes.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_referencegrants.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_grpcroutes.yaml
```

**Resultaat:**
- ✅ 5 CRDs geïnstalleerd
- ✅ `gatewayclasses`, `gateways`, `httproutes`, `grpcroutes`, `referencegrants`

**Verificatie:**
```bash
kubectl get crd | grep gateway.networking.k8s.io | wc -l
# Output: 5
```

**Documentatie:** `docs/21-gateway-api-crds.md`

**Volgende stap:** Stap 2 - Cilium Gateway API enablen

