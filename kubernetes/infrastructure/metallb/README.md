# MetalLB

Bare-metal LoadBalancer voor het homelab. Zonder MetalLB blijven `LoadBalancer` Services in status `Pending`; met MetalLB krijgen ze een IP uit de pool (192.168.178.220–230).

## Vereisten

- Cluster draait (Cilium, CoreDNS, Gateway API zoals in het stappenplan).
- DHCP-range (waar die ook draait: switch, router, …) **niet** over 192.168.178.220–230 (zie [docs/02-network.md](../../../docs/02-network.md)).

## Installatie

**1. MetalLB installeren (eenmalig)**

Vanaf jumpbox, in repo root:

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml
```

**2. IP-pool en L2-advertentie toepassen**

```bash
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
```

## Verificatie

```bash
# MetalLB pods
kubectl get pods -n metallb-system

# Test: tijdelijke LoadBalancer service
kubectl create deployment nginx-lb --image=nginx --dry-run=client -o yaml | kubectl apply -f -
kubectl expose deployment nginx-lb --type=LoadBalancer --port=80
kubectl get svc nginx-lb
# EXTERNAL-IP moet een IP uit de pool tonen (bijv. 192.168.178.220)
# Opruimen: kubectl delete deployment nginx-lb; kubectl delete svc nginx-lb
```

Zie [docs/23-metallb.md](../../../docs/23-metallb.md) voor de volledige Stap 3-instructies.
