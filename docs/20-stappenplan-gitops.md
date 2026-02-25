# Stappenplan: Van Kubernetes naar GitOps

Dit document beschrijft het pad van een werkend Kubernetes cluster naar een volledig GitOps-beheerde omgeving.

## Uitgangspunt

| Component | Status |
|-----------|--------|
| Kubernetes v1.29.2 | ✅ Draait (the Hard Way, systemd) |
| containerd | ✅ Runtime |
| Cilium 1.19.0 | ✅ CNI, kubeProxyReplacement=true |
| CoreDNS (kube-dns) | ✅ Cluster DNS 10.32.0.10 |
| Gateway API CRDs | ✅ Geïnstalleerd (Stap 1) |
| Cilium Gateway controller | ✅ Actief (GatewayClass aanwezig) |
| MetalLB | ❌ Nog niet geïnstalleerd |
| cert-manager | ❌ Nog niet geïnstalleerd |
| Argo CD | ❌ Nog niet geïnstalleerd |

## Doel

```
Internet
    │
    ▼
[Ziggo Router] ─── port forward 443 ───►  [MetalLB VIP]
                                               │
                                               ▼
                                    [Cilium Gateway + TLS]
                                         (Envoy proxy)
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
           argocd.westerweel.work    app.westerweel.work    hubble.westerweel.work
                    │
                    ▼
              [Argo CD]
                    │
                    ▼
         Git repo (declaratief)
```

---

## Stappen

### Stap 1: Gateway API CRDs

**Doel:** Gateway API Custom Resource Definitions installeren.

**Waarom:**
- Gateway API is de Kubernetes-standaard opvolger van Ingress
- CRDs moeten bestaan VOORDAT Cilium Gateway controller werkt
- Cilium installeert ze niet automatisch (bewuste keuze)
- Versie moet compatible zijn met Cilium 1.19.0

**Verificatie:**
```bash
kubectl get crd gateways.gateway.networking.k8s.io
kubectl get crd httproutes.gateway.networking.k8s.io
kubectl get crd gatewayclasses.gateway.networking.k8s.io
```

**Documentatie na voltooiing:** `docs/21-gateway-api-crds.md`

---

### Stap 2: Cilium Gateway API enablen

**Doel:** Cilium's Gateway controller activeren.

**Waarom:**
- Cilium kan Gateway resources afhandelen met ingebouwde Envoy
- Geen aparte ingress controller nodig
- Native eBPF integratie
- Je hebt Cilium al, dus minimale extra complexity

**Risico's:**
- Helm upgrade kan Cilium pods herstarten (korte interruption)
- Verkeerde values = broken networking

**Check vóór je begint (alles moet kloppen):**
```bash
kubectl get nodes
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
kubectl get pods -n kube-system -l k8s-app=hubble-relay
kubectl get crd | grep gateway.networking.k8s.io
```
→ Nodes Ready, CoreDNS Running, Cilium op alle nodes, Hubble Relay 1/1, vijf Gateway CRDs aanwezig.

**Uitvoeren:** Zie [22-cilium-gateway.md](22-cilium-gateway.md) voor commando's en Helm upgrade.

**Verificatie na Stap 2:**
```bash
kubectl get gatewayclass
# Moet "cilium" tonen met status "Accepted: True"
```

**Documentatie na voltooiing:** `docs/22-cilium-gateway.md`

---

### Stap 3: MetalLB

**Doel:** LoadBalancer IP's kunnen uitdelen op bare-metal.

**Waarom:**
- Zonder MetalLB: LoadBalancer Services blijven "Pending"
- Gateway maakt een LoadBalancer Service
- Je wilt een vast LAN IP voor de Gateway
- Dat IP kun je port-forwarden op je Ziggo router

**Risico's:**
- IP conflict met DHCP range (gebruik range buiten DHCP; zie [02-network.md](02-network.md))
- ARP issues in L2 mode

**Check vóór je begint:** Nodes Ready, GatewayClass aanwezig, Cilium draait. DHCP-range (switch/router/…) niet over 192.168.178.220–230.

**Uitvoeren:** Zie [23-metallb.md](23-metallb.md) — MetalLB manifest van upstream, daarna `kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml`.

**Verificatie:**
```bash
kubectl get svc -A -o wide | grep LoadBalancer
# EXTERNAL-IP moet een IP tonen, niet "<pending>"
```

**Documentatie na voltooiing:** `docs/23-metallb.md`

---

### Stap 4: cert-manager + DNS-01 wildcard

**Doel:** Automatische TLS certificaten van Let's Encrypt.

**Waarom:**
- HTTPS is vereist (browsers, security)
- DNS-01 challenge: geen poort 80 nodig, wildcard mogelijk
- `*.westerweel.work` dekt alle subdomeinen
- Automatische renewal

**Risico's:**
- DNS API credentials in cluster (Secret, niet in Git)
- Let's Encrypt rate limits bij veel aanvragen (wij gebruiken alleen prod)

**Check vóór je begint:** MetalLB draait; je hebt een Cloudflare API-token voor het domein.

**Uitvoeren:** Zie [24-cert-manager.md](24-cert-manager.md) — Helm install met values uit repo, Secret (Cloudflare of RFC2136), ClusterIssuer prod. Config in repo voor later Argo CD.

**Verificatie:**
```bash
kubectl get clusterissuer
kubectl get certificate -A
# Certificate status "Ready: True" na eerste aanvraag
```

**Documentatie na voltooiing:** `docs/24-cert-manager.md`

---

### Stap 5: Gateway + TLS termination

**Doel:** HTTPS Gateway die al het verkeer ontvangt.

**Waarom:**
- Centrale ingress voor alle services
- TLS termination (backends praten HTTP)
- HTTPRoutes routeren naar juiste service

**Verificatie:**
```bash
curl -v https://test.westerweel.work
# Moet valid TLS cert tonen
```

**Documentatie na voltooiing:** `docs/25-gateway-tls.md`

---

### Stap 6: Argo CD bootstrap

**Doel:** Argo CD installeren en via Gateway bereikbaar maken.

**Waarom:**
- Argo CD wordt de GitOps controller
- Alle deployments via Git
- UI voor visibility

**Verificatie:**
```bash
# Browser: https://argocd.westerweel.work
# Moet login page tonen
```

**Documentatie na voltooiing:** `docs/26-argocd-bootstrap.md`

---

### Stap 7: GitOps root app

**Doel:** App-of-apps pattern, alles onder Git beheer.

**Waarom:**
- Eén root Application beheert alle andere
- Reproduceerbaar cluster
- Self-healing (drift correctie)

**Verificatie:**
```bash
# Argo CD UI: alle apps "Synced" en "Healthy"
```

**Documentatie na voltooiing:** `docs/27-gitops-root-app.md`

---

## Voortgang

| Stap | Status | Datum |
|------|--------|-------|
| 1. Gateway API CRDs | ✅ | 2026-02-17 |
| 2. Cilium Gateway | ✅ | Al actief (GatewayClass ~6d) |
| 3. MetalLB | ⏳ | - |
| 4. cert-manager | ⏳ | - |
| 5. Gateway TLS | ⏳ | - |
| 6. Argo CD | ⏳ | - |
| 7. GitOps root | ⏳ | - |

---

## Netwerk

| Netwerk | Range | Nodes |
|---------|-------|-------|
| LAN | 192.168.178.0/24 | cp-01 (.201), node-01 (.202), node-02 (.203) |
| Pod CIDR | 10.200.0.0/16 | /24 per node |
| Service CIDR | 10.32.0.0/24 | ClusterIP's |

## Beslissingen

- **DNS Provider**: Cloudflare (voor cert-manager DNS-01)
