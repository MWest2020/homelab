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

---

### 2026-02-24 - CoreDNS toegevoegd (cluster had geen DNS)

**Probleem:** Geen CoreDNS in het cluster. Hubble Relay (en andere workloads) konden geen DNS lookups doen (timeout op 10.32.0.10:53), relay in CrashLoopBackOff.

**Actie:** CoreDNS manifests toegevoegd onder `kubernetes/infrastructure/coredns/`:
- Service **kube-dns** met `clusterIP: 10.32.0.10` (moet overeenkomen met kubelet `--cluster-dns`)
- Deployment, ConfigMap (Corefile), ServiceAccount, ClusterRole/Binding
- Zie `kubernetes/infrastructure/coredns/README.md` voor deploy en verificatie

**Deploy (vanaf jumpbox):**
```bash
kubectl apply -f kubernetes/infrastructure/coredns/
```

**Na deploy:** Hubble Relay zou automatisch moeten herstellen zodra DNS werkt.

---

### 2026-02-24 - Stap 2 documentatie: Cilium Gateway

**Actie:** Documentatie voor Stap 2 (Cilium Gateway API enablen) toegevoegd.
- **Check vóór Stap 2** in [20-stappenplan-gitops.md](20-stappenplan-gitops.md): nodes, CoreDNS, Cilium, Hubble Relay, Gateway CRDs.
- **Nieuwe doc** [22-cilium-gateway.md](22-cilium-gateway.md): dezelfde checks, Helm upgrade commando's, verificatie (`kubectl get gatewayclass`).
- Values in `cluster-config/infra/cilium/values.yaml` hebben al `gatewayAPI.enabled: true`; alleen `helm upgrade` uitvoeren.

**Achteraf:** GatewayClass stond al ~6 dagen in het cluster; Stap 2 was dus al uitgevoerd. Voortgang in stappenplan en status-overzichten bijgewerkt naar ✅.

---

### 2026-02-24 - Stap 3: MetalLB documentatie en config

**Actie:** MetalLB (Stap 3) uitwerking toegevoegd.
- **Doc** [23-metallb.md](23-metallb.md): check vóór start, install (upstream v0.14.8 manifest), IP-pool apply, verificatie.
- **IP-pool** `kubernetes/infrastructure/metallb/ip-pool.yaml`: range 192.168.178.220–230, L2 mode.
- **Netwerk** [02-network.md](02-network.md): MetalLB-range vastgelegd; DHCP mag dit bereik niet gebruiken.
- **README** in `kubernetes/infrastructure/metallb/README.md` voor snelle referentie.

**Commando's (jumpbox):**
```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
```

---

### 2026-02-24 - Stap 4: cert-manager documentatie en config

**Actie:** cert-manager (Stap 4) uitgewerkt.
- **Doc** [24-cert-manager.md](24-cert-manager.md): Cloudflare API-token, Helm install, Secret (niet in Git), ClusterIssuers staging + prod, verificatie.
- **Manifests** `kubernetes/infrastructure/cert-manager/`: `values.yaml` (Helm, in repo voor Argo CD later), `cluster-issuer-prod.yaml` (e-mail aanpassen; DNS-01: Cloudflare of RFC2136/open source). Geen staging; doc beschrijft ook alternatief zonder Cloudflare (RFC2136/BIND).

---

### 2026-02-24 - Stap 5: Gateway + TLS documentatie en manifests

**Actie:** Gateway + TLS (Stap 5) uitgewerkt voor morgen samen doornemen.
- **Doc** [25-gateway-tls.md](25-gateway-tls.md): check, volgorde (namespace → Certificate → Gateway → DNS → test-app + HTTPRoute), verificatie.
- **Manifests** `kubernetes/infrastructure/gateway/`: namespace, Certificate (*.westerweel.work), Gateway (HTTPS, Secret-ref), echo-test app + HTTPRoute voor test.westerweel.work.
- **Migratie-cutoff** in stappenplan: logisch moment is na Stap 7 (volledige stack in Git); alternatief na 5 of 6.

