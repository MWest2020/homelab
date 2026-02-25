# Cilium Gateway API

Cilium als Gateway API controller: Gateway- en HTTPRoute-resources worden afgehandeld door Cilium's ingebouwde Envoy proxy. Geen aparte ingress controller nodig.

**Voorkennis:** [21-gateway-api-crds.md](21-gateway-api-crds.md) — CRDs moeten al geïnstalleerd zijn.

---

## 1. Check vóór je begint

Draai op de jumpbox (vanaf repo root). Alles moet kloppen voordat je de Helm upgrade doet.

```bash
# Nodes
kubectl get nodes

# CoreDNS (cluster DNS)
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl get svc -n kube-system kube-dns

# Cilium (op alle nodes)
kubectl get pods -n kube-system -l k8s-app=cilium -o wide

# Hubble Relay (optioneel, voor observability)
kubectl get pods -n kube-system -l k8s-app=hubble-relay

# Gateway API CRDs (moeten bestaan)
kubectl get crd | grep gateway.networking.k8s.io
# Verwacht: 5 CRDs (gatewayclasses, gateways, httproutes, grpcroutes, referencegrants)
```

→ Alleen doorgaan als nodes Ready zijn, CoreDNS en Cilium draaien, en de vijf Gateway CRDs bestaan.

---

## 2. Helm values

In `cluster-config/infra/cilium/values.yaml` staat al:

```yaml
gatewayAPI:
  enabled: true
```

Geen wijziging nodig tenzij je Gateway expliciet uit wilt zetten.

---

## 3. Cilium upgraden (Gateway controller aanzetten)

**Vanaf de jumpbox**, in de homelab repo root:

```bash
# Repo updaten (als je wijzigingen hebt gepullt)
git pull

# Helm repo toevoegen/updaten (eenmalig of bij Cilium upgrade)
helm repo add cilium https://helm.cilium.io/
helm repo update

# Upgrade uitvoeren
helm upgrade cilium cilium/cilium -n kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

Cilium pods kunnen even herstarten; korte onderbreking van netwerkverkeer is mogelijk.

---

## 4. Verificatie

```bash
# GatewayClass "cilium" moet bestaan en Accepted
kubectl get gatewayclass

# Voorbeeld output:
# NAME     CONTROLLER                    ACCEPTED   AGE
# cilium   io.cilium/gateway-controller   True       1m
```

Optioneel: Cilium-operator en -pods controleren:

```bash
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
kubectl get pods -n kube-system -l io.cilium/app=operator
```

---

## 5. Volgende stap

Na succesvolle verificatie: **Stap 3 – MetalLB** ([20-stappenplan-gitops.md](20-stappenplan-gitops.md)). MetalLB geeft een extern IP aan de LoadBalancer Service die een Gateway later aanmaakt.

---

## Referenties / Lees verder

> **NOTE – Lees verder:** [Cilium Gateway API](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/) en [Gateway API (officieel)](https://gateway-api.sigs.k8s.io/).

| Onderwerp | Link |
|-----------|------|
| Cilium Gateway API | [docs.cilium.io](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/) |
| Gateway API | [gateway-api.sigs.k8s.io](https://gateway-api.sigs.k8s.io/) |
