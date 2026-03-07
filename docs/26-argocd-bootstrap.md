# Argo CD – Stap 6

Argo CD is de GitOps controller. Vanaf hier gaan alle deployments via Git.

**Stappenplan:** [20-stappenplan-gitops.md](20-stappenplan-gitops.md)

---

## Vereisten

- Gateway + TLS werkt (Stap 5)
- `gateway-system/main-gateway` heeft `allowedRoutes.namespaces.from: All` (anders werkt cross-namespace HTTPRoute niet)

---

## Installatie (Helm, config in repo)

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  -f kubernetes/infrastructure/argocd/values.yaml

kubectl wait deployment argocd-server -n argocd \
  --for=condition=available --timeout=180s

kubectl apply -f kubernetes/infrastructure/argocd/httproute.yaml
```

**Values** (`kubernetes/infrastructure/argocd/values.yaml`):
- `server.insecure: "true"` — TLS wordt afgehandeld door de Gateway
- `server.ingress.enabled: false` — Gateway API HTTPRoute, geen built-in ingress

---

## DNS

Geen publiek DNS-record nodig. Toegang via LAN of Tailscale subnet router:

- **LAN / Tailscale:** `/etc/hosts` → `192.168.178.220  argocd.westerweel.work`
- **Jumpbox** heeft al dit entry en Tailscale subnet routing (`192.168.178.0/24`)

---

## Eerste login

```bash
# Initieel admin wachtwoord (eenmalig; daarna wijzigen of admin disablen)
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d && echo
```

Gebruikersnaam: `admin`. Wijzig het wachtwoord direct na eerste login.

---

## Bekende issues

### 1. Gateway accepteert HTTPRoute uit andere namespace niet

`allowedRoutes.namespaces.from: All` moet op de listener in `gateway.yaml` staan.
Zonder dit blijft de HTTPRoute unaccepted en is Argo CD niet bereikbaar.

### 2. MetalLB kondigt IP niet aan na Cilium Gateway install

Symptoom: `ping 192.168.178.220` geeft 100% packet loss.

Cilium's Gateway controller maakt een EndpointSlice zonder het `kubernetes.io/service-name` label dat MetalLB vereist. Fix (eenmalig na install):

```bash
kubectl label endpointslice cilium-gateway-main-gateway \
  -n gateway-system \
  kubernetes.io/service-name=cilium-gateway-main-gateway
```

### 3. Cilium GatewayClass verdwijnt na herstart operator

Als de Cilium operator start vóór de Gateway API CRDs beschikbaar zijn, maakt hij geen GatewayClass aan. Fix:

```bash
helm upgrade cilium cilium/cilium -n kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

---

## Verificatie

```bash
kubectl get pods -n argocd
kubectl get httproute argocd -n argocd
kubectl get gateway main-gateway -n gateway-system
# PROGRAMMED: True

curl -sk https://argocd.westerweel.work | grep -o "<title>.*</title>"
# <title>Argo CD</title>
```

---

## Volgende stap

**Stap 7 – GitOps root app** ([20-stappenplan-gitops.md](20-stappenplan-gitops.md)): app-of-apps pattern, alles onder Git-beheer.
