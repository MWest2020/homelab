# cert-manager – config in repo

Cert-manager wordt geïnstalleerd met Helm; **config (values + ClusterIssuer) staat in deze repo**, zodat het later in Argo CD kan.

- **values.yaml** – Helm values (o.a. CRDs); install met `-f kubernetes/infrastructure/cert-manager/values.yaml`.
- **cluster-issuer-prod.yaml** – Let's Encrypt prod; e-mail aanpassen; DNS-01: Cloudflare of [RFC2136/andere](https://cert-manager.io/docs/configuration/acme/dns01/).
- Geen secrets in Git (Cloudflare-token of RFC2136 TSIG handmatig aanmaken).

## Install (eenmalig)

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace -f kubernetes/infrastructure/cert-manager/values.yaml
```

## ClusterIssuer (alleen prod)

1. Pas in `cluster-issuer-prod.yaml` `spec.acme.email` aan.
2. Gebruik Cloudflare (secret `cloudflare-api-token`) of RFC2136/andere solver (zie [docs/24-cert-manager.md](../../../docs/24-cert-manager.md)).
3. `kubectl apply -f kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml`

## Later: Argo CD

Argo CD Application kan de Jetstack-chart gebruiken met onze values uit deze dir. Buiten scope voor nu.

> **NOTE – Lees verder:** [cert-manager](https://cert-manager.io/docs/), [DNS-01 providers](https://cert-manager.io/docs/configuration/acme/dns01/) (o.a. RFC2136 voor open source/BIND).
