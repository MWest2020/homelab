# Gateway + TLS – Stap 5

Eén HTTPS-Gateway die al het verkeer op 443 ontvangt, TLS beëindigt en naar backends routeert via HTTPRoutes. Hier komen MetalLB, Cilium en cert-manager samen. Na deze stap plannen we migratie (Hard Way → kubeadm).

**Stappenplan:** [20-stappenplan-gitops.md](20-stappenplan-gitops.md)

> **NOTE – Lees verder:** [Cilium Gateway API HTTPS](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/https/), [Gateway API TLS](https://gateway-api.sigs.k8s.io/guides/tls/).

---

## 1. Check vóór je begint

Je hebt nog **geen** namespace `gateway-system` – die maak je in stap 2 aan. Je hebt ook nog **geen** IP voor DNS; dat krijg je pas na stap 4.

- **MetalLB:** LoadBalancer-services krijgen een IP (`kubectl get svc -A | grep LoadBalancer`).
- **cert-manager:** ClusterIssuer `letsencrypt-prod` Ready (`kubectl get clusterissuer`).
- **DNS:** Pas invullen **nadat** de Gateway een EXTERNAL-IP heeft (stap 5).

---

## 2. Alle stappen in volgorde

Alles vanaf **repo root** op de jumpbox (`~/homelab` of waar de repo staat). Map: `kubernetes/infrastructure/gateway/`.

---

**Stap 1 – Namespace + Certificate**

Namespace `gateway-system` en het Certificate (cert-manager vraagt het TLS-cert aan via DNS-01). Het certificaat kan 1–2 minuten duren.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/namespace.yaml
kubectl apply -f kubernetes/infrastructure/gateway/certificate.yaml
```

Wacht tot het certificaat Ready is:

```bash
kubectl get certificate -n gateway-system -w
# westerweel-work-tls: Ready=True → Ctrl+C
```

---

**Stap 2 – Gateway**

De Gateway gebruikt de Secret die cert-manager net heeft aangemaakt. Cilium maakt hierna een LoadBalancer Service.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/gateway.yaml
```

---

**Stap 3 – Wacht op LoadBalancer IP**

De Gateway krijgt een Service met EXTERNAL-IP van MetalLB. Zonder dit IP kun je nog geen DNS invullen.

```bash
kubectl get svc -n gateway-system
# Zoek de Service (naam hangt van Cilium af, bijv. main-gateway of gateway-main-gateway).
# EXTERNAL-IP moet een IP zijn (bijv. 192.168.178.220), niet <pending>.
```

Noteer dit **EXTERNAL-IP** (bijv. `192.168.178.220`).

---

**Stap 4 – Test-app + HTTPRoute**

De echo-app en de route voor `test.westerweel.work`. Deze kun je al toepassen; ze werken zodra DNS staat.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/gateway-test-app.yaml
kubectl apply -f kubernetes/infrastructure/gateway/httproute-test.yaml
```

---

**Stap 5 – DNS (nu heb je het IP)**

Nu kun je het IP ontvangen/gebruiken voor DNS:

- In **Cloudflare** (of je DNS): A-record **test.westerweel.work** → het EXTERNAL-IP uit stap 3 (bijv. 192.168.178.220).
- Of lokaal testen: in **/etc/hosts** op je laptop: `192.168.178.220 test.westerweel.work`.

---

**Stap 6 – Verificatie**

```bash
# Gateway listeners OK?
kubectl get gateway -n gateway-system

# HTTPS (na DNS-propagation of /etc/hosts)
curl -v https://test.westerweel.work
# Moet geldig TLS-cert (Let's Encrypt) en antwoord van de echo-server tonen.
```

Optioneel: op je router poort **443** forwarden naar het EXTERNAL-IP als je vanaf internet wilt bereiken.

---

## 3. Wat staat waar

| Bestand | Doel |
|---------|------|
| `namespace.yaml` | Namespace `gateway-system` |
| `certificate.yaml` | cert-manager Certificate voor `*.westerweel.work` + `westerweel.work` |
| `gateway.yaml` | Gateway (HTTPS, poort 443, TLS via Secret) |
| `gateway-test-app.yaml` | Deployment + Service echo-test |
| `httproute-test.yaml` | HTTPRoute: test.westerweel.work → echo-test |

Later voeg je voor andere hostnames (bijv. argocd.westerweel.work) nieuwe HTTPRoutes toe en eventueel extra listeners of hetzelfde wildcard-cert gebruiken.

---

## 4. Volgende stap

**Stap 6 – Argo CD** ([20-stappenplan-gitops.md](20-stappenplan-gitops.md)): Argo CD installeren en bereikbaar maken via de Gateway (bijv. argocd.westerweel.work).

---

## Referenties / Lees verder

| Onderwerp | Link |
|-----------|------|
| Cilium Gateway HTTPS | [docs.cilium.io](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/https/) |
| Gateway API TLS | [gateway-api.sigs.k8s.io](https://gateway-api.sigs.k8s.io/guides/tls/) |
