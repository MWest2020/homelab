# Gateway + TLS (Stap 5)

Eén HTTPS-Gateway met TLS (cert-manager) en HTTPRoutes. Zie [docs/25-gateway-tls.md](../../../docs/25-gateway-tls.md) voor de volledige walkthrough.

## Volgorde apply

1. `namespace.yaml` + `certificate.yaml` → wacht tot Certificate Ready
2. `gateway.yaml` → noteer EXTERNAL-IP van de Gateway-Service
3. DNS: test.westerweel.work → dat EXTERNAL-IP
4. `gateway-test-app.yaml` + `httproute-test.yaml`

## Verificatie

```bash
curl -v https://test.westerweel.work
```

> **NOTE – Lees verder:** [Cilium Gateway HTTPS](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/https/).
