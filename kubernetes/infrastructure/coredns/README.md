# CoreDNS - Cluster DNS

Cluster DNS voor Kubernetes the Hard Way. Zonder CoreDNS kunnen pods geen service/hostnames resolven (o.a. `*.svc.cluster.local`).

## Vereisten

- Cluster DNS IP **10.32.0.10** moet overeenkomen met `--cluster-dns` op alle kubelets. Zie [docs/02-network.md](../../../docs/02-network.md).

## Deployen

Vanaf de repo root (of vanaf de jumpbox met gekloonde repo):

```bash
kubectl apply -f kubernetes/infrastructure/coredns/
```

## Verificatie

```bash
# CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Service (moet 10.32.0.10 zijn)
kubectl get svc -n kube-system kube-dns

# DNS test vanuit een pod
kubectl run dns-test --rm -it --restart=Never --image=busybox:1.36 -- nslookup kubernetes.default.svc.cluster.local
```

## Versie

- CoreDNS image: `registry.k8s.io/coredns/coredns:v1.11.1`
