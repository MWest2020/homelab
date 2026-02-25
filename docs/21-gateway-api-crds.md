# Gateway API CRDs

## Wat is Gateway API?

Gateway API is de Kubernetes-standaard opvolger van Ingress. Het biedt:
- Meer expressieve routing (headers, query params, etc.)
- Rol-gebaseerde scheiding (platform team vs app team)
- Ondersteuning voor TCP/UDP (niet alleen HTTP)
- Standaard across alle controllers (Cilium, Envoy, Nginx, etc.)

## Waarom handmatig installeren?

Cilium (en de meeste Gateway controllers) installeren de CRDs **niet automatisch**. Dit is een bewuste keuze:
- Jij bepaalt welke versie je draait
- Voorkomt versieconflicten bij meerdere controllers
- CRDs zijn cluster-wide, niet namespace-scoped

## Geïnstalleerde CRDs

| CRD | Beschrijving |
|-----|--------------|
| `gatewayclasses` | Definieert welke controller Gateways beheert |
| `gateways` | Entry point voor verkeer (zoals een LoadBalancer) |
| `httproutes` | HTTP routing regels (host, path, headers) |
| `grpcroutes` | gRPC routing regels |
| `referencegrants` | Cross-namespace toegang (security) |

## Versie Compatibility

| Cilium | Gateway API |
|--------|-------------|
| 1.19.x | v1.2.0 |
| 1.18.x | v1.1.0 |
| 1.17.x | v1.0.0 |

Wij gebruiken: **Cilium 1.19.0** + **Gateway API v1.2.0**

## Installatie

```bash
# Standard channel CRDs (stabiel)
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_gatewayclasses.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_gateways.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_httproutes.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_referencegrants.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/v1.2.0/config/crd/standard/gateway.networking.k8s.io_grpcroutes.yaml
```

## Verificatie

```bash
# Moet 5 CRDs tonen
kubectl get crd | grep gateway.networking.k8s.io

# Output:
# gatewayclasses.gateway.networking.k8s.io     2026-02-17T19:16:30Z
# gateways.gateway.networking.k8s.io           2026-02-17T19:16:30Z
# grpcroutes.gateway.networking.k8s.io         2026-02-17T19:16:32Z
# httproutes.gateway.networking.k8s.io         2026-02-17T19:16:31Z
# referencegrants.gateway.networking.k8s.io    2026-02-17T19:16:32Z
```

## Volgende stap

CRDs zijn aanwezig, maar er is nog geen **GatewayClass**. Die wordt aangemaakt door Cilium zodra we Gateway API enablen in de Cilium configuratie.

Zie: [22-cilium-gateway.md](22-cilium-gateway.md)

> **NOTE – Lees verder:** [Gateway API (officieel)](https://gateway-api.sigs.k8s.io/) en [Cilium Gateway API](https://docs.cilium.io/en/v1.19/network/servicemesh/gateway-api/).

## Referenties / Lees verder

| Onderwerp | Link |
|-----------|------|
| Gateway API | [gateway-api.sigs.k8s.io](https://gateway-api.sigs.k8s.io/) |
| Cilium Gateway API | [docs.cilium.io](https://docs.cilium.io/en/v1.19/network/servicemesh/gateway-api/) |
| Gateway API releases | [GitHub](https://github.com/kubernetes-sigs/gateway-api/releases) |
