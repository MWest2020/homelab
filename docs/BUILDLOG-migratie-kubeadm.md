# Build log – Migratie Hard Way → kubeadm

Bij **handmatige** uitrol van de migratie kun je per fase hier noteren wat je gedaan hebt en wat de output was. Zo is de migratie de volgende keer (of door iemand anders) te volgen of te herhalen.

**Migratiedoc:** [30-migratie-kubeadm.md](30-migratie-kubeadm.md)  
**Ansible-optie:** Zie sectie "Automatisering met Ansible" in die doc.

---

## Context van deze run

| Veld | Ingevuld |
|------|----------|
| Datum start | … |
| Cluster vóór migratie | Hard Way (systemd) |
| Nodes | cp-01, node-01, node-02 |
| Uitgevoerd door | … |

---

## Fase A – Huidige staat vastleggen

**Datum:** …

**Commando's (jumpbox):**
```bash
kubectl get ns
kubectl get pods -A -o wide
kubectl get secrets -A | grep -E 'cert-manager|gateway'
kubectl get svc -n gateway-system
```

**Notities / EXTERNAL-IP genoteerd:** …

---

## Fase B – Hard Way-cluster stoppen

**Datum:** …

**Op cp-01:**
```bash
sudo systemctl stop kube-apiserver kube-controller-manager kube-scheduler etcd kubelet
sudo systemctl disable kube-apiserver kube-controller-manager kube-scheduler etcd kubelet
```

**Op node-01, node-02:**
```bash
sudo systemctl stop kubelet
sudo systemctl disable kubelet
```

**Optioneel schoonmaken uitgevoerd?** ja / nee  

**Notities:** …

---

## Fase C – kubeadm, kubelet, kubectl installeren

**Datum:** …

**Methode:** handmatig / Ansible (`ansible-playbook playbooks/kubeadm-install-packages.yml`)

**Handmatig (per node):** welke repo (apt/dnf), welke versie: …

**Output (eerste node):** …
```text
...
```

---

## Fase D – kubeadm init (cp-01)

**Datum:** …

**Commando:**
```bash
sudo kubeadm init \
  --control-plane-endpoint 192.168.178.201:6443 \
  --pod-network-cidr 10.200.0.0/16 \
  --service-cidr 10.32.0.0/24
```

**Join-command genoteerd (voor Fase E):** …
```text
kubeadm join 192.168.178.201:6443 --token ... --discovery-token-ca-cert-hash sha256:...
```

**Kubeconfig op cp-01:**
```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

**Notities:** …

---

## Fase E – kubeadm join (workers)

**Datum:** …

**Methode:** handmatig / Ansible (`ansible-playbook playbooks/kubeadm-bootstrap.yml` had Fase D+E gedaan)

**node-01 join output:** …
**node-02 join output:** …

**Verificatie:**
```bash
kubectl get nodes
```
**Output:** …

---

## Fase F – Cilium

**Datum:** …

**Commando's (repo root, jumpbox of cp-01):**
```bash
helm repo add cilium https://helm.cilium.io/
helm repo update
helm upgrade --install cilium cilium/cilium --namespace kube-system -f cluster-config/infra/cilium/values.yaml
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
kubectl get nodes
```

**Notities:** …

---

## Fase G – Gateway API CRDs

**Datum:** …

**Commando:**
```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml
kubectl get crd | grep gateway
```

**Notities:** …

---

## Fase H – MetalLB

**Datum:** …

**Commando's:**
```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml
# eventueel: webhooks verwijderen bij timeout
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
```

**Webhook-timeout?** ja / nee  

**Notities:** …

---

## Fase I – cert-manager + ClusterIssuer + Secret

**Datum:** …

**Helm + ClusterIssuer:**
```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm upgrade --install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace -f kubernetes/infrastructure/cert-manager/values.yaml
kubectl create secret generic cloudflare-api-token --from-literal=api-token=... --namespace cert-manager
kubectl apply -f kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml
```

**Secret handmatig aangemaakt (niet in Git).**  

**Notities:** …

---

## Fase J – Gateway-stack

**Datum:** …

**Commando's:**
```bash
kubectl apply -f kubernetes/infrastructure/gateway/namespace.yaml
kubectl apply -f kubernetes/infrastructure/gateway/certificate.yaml
# wacht: kubectl get certificate -n gateway-system -w
kubectl apply -f kubernetes/infrastructure/gateway/gateway.yaml
kubectl get svc -n gateway-system
# EXTERNAL-IP: …
kubectl apply -f kubernetes/infrastructure/gateway/gateway-test-app.yaml
kubectl apply -f kubernetes/infrastructure/gateway/httproute-test.yaml
```

**EXTERNAL-IP genoteerd:** …  
**DNS A-record / port-forward gecontroleerd:** …

---

## Fase K – Kubeconfig op jumpbox

**Datum:** …

**Hoe:** scp admin.conf van cp-01 naar jumpbox `~/.kube/config`  

**Verificatie:** `kubectl get nodes` vanaf jumpbox: …

---

## Fase L – Verificatie

**Datum:** …

**Nodes:** `kubectl get nodes` → …  
**HTTPS-test:** `curl -v https://test.westerweel.work` → …

**Migratie geslaagd:** ja / nee  

**Overige notities:** …
