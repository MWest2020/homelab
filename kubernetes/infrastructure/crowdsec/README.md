# CrowdSec – config in repo (fase B, K8s)

CrowdSec op het cluster wordt met Helm geïnstalleerd; **config (values) staat in
deze repo**, zodat het later in Argo CD kan. Dit is **fase B** uit
[`learning/crowdsec.md`](../../../../learning/crowdsec.md); fase A (CrowdSec op
de Caddy-proxy-VM) draait los daarvan.

- **values.yaml** – Helm values; engine + chart gepind (chart `0.24.0` → engine
  `v1.7.8`).
- **Logbron** = container-logs via de agent-DaemonSet. Waarom niet Envoy/Hubble:
  zie de comment boven in `values.yaml`.
- **Geen secrets in Git** – Console-enrollment doe je post-deploy met `cscli`.
- **Vereist een default StorageClass** (LAPI gebruikt PVC's). Het homelab-cluster
  heeft `local-path`.

## Install (eenmalig)

```bash
helm repo add crowdsec https://crowdsecurity.github.io/helm-charts
helm repo update crowdsec
helm upgrade --install crowdsec crowdsec/crowdsec -n crowdsec --create-namespace \
  --version 0.24.0 -f kubernetes/infrastructure/crowdsec/values.yaml
```

## Verifieer

```bash
kubectl -n crowdsec get pods
# LAPI-pod heet meestal crowdsec-lapi-* (check met de regel hierboven):
LAPI=$(kubectl -n crowdsec get pod -l type=lapi -o name | head -1)
kubectl -n crowdsec exec "$LAPI" -- cscli lapi status
kubectl -n crowdsec exec "$LAPI" -- cscli metrics
```

## Console-enrollment (optioneel)

Zelfde CrowdSec Console als de proxy. Geen key in Git — enroll post-deploy:

```bash
kubectl -n crowdsec exec "$LAPI" -- cscli console enroll --quick --name k8s-cluster
```

Open de geprinte link in een browser waar je op app.crowdsec.net ingelogd bent
en keur de pending engine goed.

## Acquisition aanzetten (zodra er een web-app staat)

Nu staat `agent.acquisition` leeg → de agent idlet. Zodra Nextcloud (of een
andere web-app met access-logs) op het cluster landt, zet je in `values.yaml`
de bijbehorende acquisition aan (namespace/podName/program) en draai je
`helm upgrade` opnieuw.

## Later: Argo CD

Een Argo CD Application kan de crowdsec-chart met deze values gebruiken. Buiten
scope voor nu (app-of-apps = stap 7 van de GitOps-roadmap).

> **NOTE:** [CrowdSec K8s-install](https://docs.crowdsec.net/u/getting_started/installation/kubernetes/),
> [data sources](https://docs.crowdsec.net/docs/next/data_sources/intro). Fase B.2
> (ext_authz / WAF op de Cilium-Gateway) staat in `learning/crowdsec.md`.
