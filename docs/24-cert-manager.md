# cert-manager – Stap 4

Automatische TLS-certificaten via Let's Encrypt. Met **DNS-01** heb je geen poort 80 nodig en kun je **wildcards** aanvragen (bijv. `*.westerweel.work`).

**Stappenplan:** [20-stappenplan-gitops.md](20-stappenplan-gitops.md)

> **NOTE – Lees verder:** [cert-manager docs](https://cert-manager.io/docs/), [ACME DNS-01](https://cert-manager.io/docs/configuration/acme/dns01/).

---

## 1. Check vóór je begint

- MetalLB draait (Stap 3).
- E-mailadres voor Let's Encrypt (verlopen/waarschuwingen).
- DNS-01: je hebt een manier om TXT-records te zetten voor je domein (Cloudflare, RFC2136/BIND, of andere [ondersteunde provider](https://cert-manager.io/docs/configuration/acme/dns01/)).

---

## 2. cert-manager installeren (Helm, config in repo)

Alle cert-manager-config staat in de repo (`kubernetes/infrastructure/cert-manager/`), zodat dit later via Argo CD kan. De Helm-chart zelf komt van Jetstack; onze **values** en **ClusterIssuer** liggen in de repo.

**Vanaf de jumpbox**, in de homelab repo root:

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  -f kubernetes/infrastructure/cert-manager/values.yaml
```

Wacht tot de pods Running zijn:

```bash
kubectl get pods -n cert-manager -w
```

**Later (Argo CD):** Een Argo CD Application kan dezelfde chart + onze values uit de repo gebruiken (chart: jetstack/cert-manager, values from repo). Nu buiten scope.

---

## 3. ClusterIssuer – alleen prod

We gebruiken alleen **letsencrypt-prod** (geen staging). Pas in `cluster-issuer-prod.yaml` het e-mailadres aan en kies één van de onderstaande DNS-01 opties.

### Optie A: Cloudflare (eenvoudig)

1. Cloudflare: **My Profile** → **API Tokens** → Create Token (Zone – Zone Read, Zone – DNS Edit).
2. Secret aanmaken (token **niet** in Git):

   ```bash
   kubectl create secret generic cloudflare-api-token \
     --from-literal=api-token=JOUW_TOKEN \
     --namespace cert-manager
   ```

3. ClusterIssuer in de repo gebruikt al Cloudflare (`apiTokenSecretRef`). Alleen e-mail in YAML aanpassen.

> **NOTE – Lees verder:** [Cloudflare DNS-01](https://cert-manager.io/docs/configuration/acme/dns01/cloudflare/).

### Optie B: Zonder Cloudflare – open source (RFC2136 / BIND)

Met **RFC2136** praat cert-manager met een DNS-server die dynamische updates ondersteunt (bijv. **BIND** of **Knot DNS**). Geen vendor lock-in; alles open source.

- Je hebt een BIND (of andere RFC2136)-server met een zone voor je domein.
- Op die server: TSIG-key aanmaken, zone toestaan voor updates met die key.
- In cert-manager: ClusterIssuer met `dns01.rfc2136` (nameserver, TSIG secret). Geen Cloudflare-token.

Voorbeeld-solver (naast of in plaats van Cloudflare in je ClusterIssuer):

```yaml
solvers:
  - dns01:
      rfc2136:
        nameserver: 192.168.178.1   # je BIND server
        tsigSecretSecretRef:
          name: rfc2136-tsig
          key: tsig-key
        tsigKeyName: "acme-key."
```

Secret voor TSIG: `kubectl create secret generic rfc2136-tsig --from-literal=tsig-key=... -n cert-manager`.

> **NOTE – Lees verder:** [cert-manager RFC2136](https://cert-manager.io/docs/configuration/acme/dns01/rfc2136/). Zie ook [DNS-01 overzicht](https://cert-manager.io/docs/configuration/acme/dns01/) voor andere open/providers (o.a. PowerDNS, CoreDNS-webhook).

---

## 4. ClusterIssuer toepassen

Pas in `kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml` **spec.acme.email** aan, en (als je niet Cloudflare gebruikt) de **solvers** naar RFC2136 of een andere [DNS-01 provider](https://cert-manager.io/docs/configuration/acme/dns01/). Daarna:

```bash
kubectl apply -f kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml
```

**Webhook-timeout** (`failed calling webhook "webhook.cert-manager.io" ... Timeout exceeded`): op "Kubernetes the Hard Way" kan de API-server de cert-manager-webhook (ClusterIP) soms niet bereiken. Workaround:

```bash
kubectl get validatingwebhookconfiguration -o name | grep cert-manager | xargs -r kubectl delete
kubectl apply -f kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml
```

---

## 5. Verificatie

```bash
kubectl get clusterissuer
# letsencrypt-prod moet Ready
kubectl get certificate -A
# Na eerste Certificate-resource: status Ready: True
```

---

## 6. Volgende stap

**Stap 5 – Gateway + TLS** ([20-stappenplan-gitops.md](20-stappenplan-gitops.md)): Gateway met TLS en een Certificate dat `letsencrypt-prod` gebruikt.

---

## Referenties / Lees verder

| Onderwerp | Link |
|-----------|------|
| cert-manager | [cert-manager.io](https://cert-manager.io/docs/) |
| Helm install | [cert-manager Helm](https://cert-manager.io/docs/installation/helm/) |
| DNS-01 (alle providers) | [DNS01](https://cert-manager.io/docs/configuration/acme/dns01/) |
| Cloudflare | [Cloudflare](https://cert-manager.io/docs/configuration/acme/dns01/cloudflare/) |
| RFC2136 (BIND, open source) | [RFC2136](https://cert-manager.io/docs/configuration/acme/dns01/rfc2136/) |
