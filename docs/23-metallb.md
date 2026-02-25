# MetalLB – Stap 3

LoadBalancer-IP's op bare-metal. Nodig zodat een Cilium Gateway later een Service type LoadBalancer kan krijgen met een vast LAN-IP (voor port-forward op de router).

MetalLB kan in twee modi: **Layer 2 (L2)** met ARP/NDP, of **BGP** (vereist BGP-router). Wij gebruiken **L2**: geen routerconfig nodig, werkt op elk LAN. De `L2Advertisement` in onze config zorgt daarvoor; de `IPAddressPool` definieert alleen het adresbereik.

> **NOTE – Lees verder:** [MetalLB Configuration (L2 vs BGP)](https://metallb.io/configuration/) in de officiële documentatie.

**Stappenplan:** [20-stappenplan-gitops.md](20-stappenplan-gitops.md)

---

## 1. Check vóór je begint

```bash
kubectl get nodes
kubectl get gatewayclass
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
```

→ Nodes Ready, GatewayClass `cilium` aanwezig, Cilium op alle nodes.

**Netwerk:** De pool 192.168.178.220–230 moet **buiten** de DHCP-range vallen van wat bij jou DHCP doet (switch, router, etc.). Zie [02-network.md](02-network.md). Zo niet: pas de DHCP-range daar aan, of wijzig het bereik in `kubernetes/infrastructure/metallb/ip-pool.yaml`.

---

## 2. MetalLB installeren

**Vanaf de jumpbox**, in de homelab repo root.

**Stap 2a – MetalLB controller + speaker (eenmalig):**

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml
```

Wacht tot de pods in `metallb-system` Running zijn:

```bash
kubectl get pods -n metallb-system -w
# Ctrl+C als controller en speakers (alle nodes) Running zijn
```

**Stap 2b – IP-pool en L2-advertentie (onze config):**

```bash
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
```

De pool `homelab-lan` gebruikt 192.168.178.220–192.168.178.230. L2 mode: MetalLB antwoordt met ARP op dat bereik vanaf een van de nodes.

> **NOTE – Lees verder:** [L2 configuration (interfaces, node selectors)](https://metallb.io/configuration/_advanced_l2_configuration/) in de officiële MetalLB-docs.

**Als je een webhook-timeout krijgt** (`failed calling webhook ... context deadline exceeded`): op "Kubernetes the Hard Way" kan de API-server (op de control plane host) de MetalLB-webhook (ClusterIP) soms niet bereiken. Workaround: webhooks tijdelijk uitzetten, pool toepassen, daarna eventueel webhooks weer aan.

```bash
kubectl get validatingwebhookconfiguration -o name | grep metallb | xargs -r kubectl delete
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
# Optioneel: webhooks weer aan → opnieuw metallb-native.yaml toepassen
```

---

## 3. Verificatie

**LoadBalancer krijgt een IP:**

```bash
kubectl get svc -A -o wide | grep LoadBalancer
```

Als er nog geen LoadBalancer-service is: maak een testservice, controleer EXTERNAL-IP en ruim weer op:

```bash
kubectl create deployment nginx-lb --image=nginx
kubectl expose deployment nginx-lb --type=LoadBalancer --port=80
kubectl get svc nginx-lb
# EXTERNAL-IP moet 192.168.178.220 of volgende in de pool zijn
kubectl delete deployment nginx-lb
kubectl delete svc nginx-lb
```

**MetalLB-pods:**

```bash
kubectl get pods -n metallb-system
# controller: 1/1, speaker: 1 per node
```

---

## 4. Volgende stap

**Stap 4 – cert-manager** ([20-stappenplan-gitops.md](20-stappenplan-gitops.md)): TLS-certificaten (Let's Encrypt, DNS-01) voor Gateway/HTTPS.

---

## Referenties / Lees verder

| Onderwerp | Link |
|-----------|------|
| MetalLB (homepage) | [metallb.io](https://metallb.io/) |
| Configuration (L2, BGP) | [metallb.io/configuration](https://metallb.io/configuration/) |
| FAQ (o.a. L2, ARP) | [metallb.io/faq](https://metallb.io/faq/) |
| Homelab netwerk (pool-range) | [02-network.md](02-network.md#metallb-loadbalancer-vips) |
