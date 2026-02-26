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

## 2. Alle stappen in volgorde (met toelichting)

Alles vanaf **repo root** op de jumpbox (`~/homelab`). Map: `kubernetes/infrastructure/gateway/`.

---

**Stap 1 – Namespace aanmaken**

**Wat:** Een aparte namespace `gateway-system` voor de Gateway, het certificaat en de test-app.  
**Waarom:** Alles rond ingress (Gateway, Certificate, HTTPRoutes) bij elkaar; de Gateway moet in dezelfde namespace als de TLS-Secret (die cert-manager aanmaakt) staan.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/namespace.yaml
```

---

**Stap 2 – Certificate aanmaken**

**Wat:** Een cert-manager **Certificate** voor `*.westerweel.work` en `westerweel.work`. Cert-manager gebruikt de bestaande ClusterIssuer `letsencrypt-prod` en doet een **DNS-01** challenge (zet tijdelijk een TXT-record bij Cloudflare, Let's Encrypt checkt dat, daarna krijgt je cluster het cert). Het resultaat komt in een **Secret** `westerweel-work-tls` in dezelfde namespace.  
**Waarom:** De Gateway heeft bij TLS een verwijzing naar een Secret (cert + key) nodig. Die Secret bestaat pas nadat dit Certificate **Ready** is. Daarom eerst Certificate, daarna pas de Gateway.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/certificate.yaml
```

Wacht tot het certificaat Ready is (kan 1–2 minuten duren):

```bash
kubectl get certificate -n gateway-system -w
# westerweel-work-tls: Ready=True → Ctrl+C
```

---

**Stap 3 – Gateway aanmaken**

**Wat:** Een **Gateway**-resource (Gateway API) met één HTTPS-listener op poort 443, die de TLS-Secret `westerweel-work-tls` gebruikt. Cilium (GatewayClass `cilium`) pakt dit op en maakt o.a. een **LoadBalancer Service** voor deze Gateway.  
**Waarom:** Dit is de “voordeur”: alle HTTPS-verkeer naar dat IP komt bij deze Gateway binnen; Cilium beëindigt TLS en kijkt in HTTPRoutes naar welke backend de request moet.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/gateway.yaml
```

---

**Stap 4 – LoadBalancer-IP noteren**

**Wat:** Cilium heeft een Service voor de Gateway aangemaakt. MetalLB geeft daar een **EXTERNAL-IP** aan (uit de pool 192.168.178.220–230).  
**Waarom:** Dat IP is het adres waarop je Gateway bereikbaar is. Pas als je dit IP weet, kun je DNS (of /etc/hosts) invullen; zonder IP heeft een A-record geen waarde.

```bash
kubectl get svc -n gateway-system
# Zoek de Service (naam hangt van Cilium af, bijv. main-gateway).
# EXTERNAL-IP moet een IP zijn (bijv. 192.168.178.220), niet <pending>.
```

Noteer dit **EXTERNAL-IP**.

---

**Stap 5 – Test-app + HTTPRoute**

**Wat:** Een kleine **Deployment** (echo-server) met **Service** `echo-test`, en een **HTTPRoute** die zegt: voor host `test.westerweel.work` stuur al het verkeer naar die Service.  
**Waarom:** De Gateway alleen doet nog niks met verkeer; er moet een Route zijn die aan een backend koppelt. Met deze route kun je straks `https://test.westerweel.work` testen.

```bash
kubectl apply -f kubernetes/infrastructure/gateway/gateway-test-app.yaml
kubectl apply -f kubernetes/infrastructure/gateway/httproute-test.yaml
```

---

**Stap 6 – DNS (nu heb je het IP)**

**Wat:** Zorg dat **test.westerweel.work** naar het EXTERNAL-IP uit stap 4 wijst.  
**Waarom:** De browser of `curl` moet dat hostname kunnen resolven naar het IP van je Gateway; anders komt het verkeer niet bij je cluster.

- In **Cloudflare** (of je DNS): A-record **test.westerweel.work** → het EXTERNAL-IP (bijv. 192.168.178.220).
- Of lokaal: in **/etc/hosts** op je laptop: `192.168.178.220 test.westerweel.work`.

---

**Stap 7 – Verificatie**

**Wat:** Controleren of de Gateway klaar is en of HTTPS naar de echo-app werkt.  
**Waarom:** Zo zie je dat de hele keten (DNS → MetalLB → Gateway → TLS → HTTPRoute → Service) goed staat.

```bash
kubectl get gateway -n gateway-system
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
