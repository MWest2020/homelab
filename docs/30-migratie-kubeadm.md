# Migratie: Kubernetes the Hard Way → kubeadm

Dit document beschrijft de **exacte stappen** om het bestaande cluster (Kubernetes the Hard Way, systemd) te **vervangen** door een kubeadm-cluster op **dezelfde hosts**. Er draaien geen twee clusters naast elkaar: je stopt het oude cluster en brengt op dezelfde machines het nieuwe cluster omhoog. De jumpbox, hostnamen en IP’s blijven gelijk; alleen de cluster-inhoud wordt opnieuw opgezet.

**Stappenplan:** [20-stappenplan-gitops.md](20-stappenplan-gitops.md)

---

## 1. Waarom zo (geen twee clusters naast elkaar)

- **Eén kubelet per node:** Op dezelfde fysieke/virtuele machine kun je niet twee clusters laten draaien; elke node hoort bij één cluster.
- **Zelfde hosts = vervanging:** cp-01 (192.168.178.201), node-01 (192.168.178.202), node-02 (192.168.178.203) en de jumpbox blijven. Je bouwt het **nieuwe** cluster op deze machines en gebruikt daarna alleen dat cluster. Er is **downtime** tijdens de overstap (ongeveer 30–60 minuten, afhankelijk van hoe snel je de stappen doorloopt).
- **Jumpbox blijft:** Na de migratie gebruik je weer `kubectl` vanaf de jumpbox; de kubeconfig wijst naar dezelfde API-endpoint (cp-01:6443). Geen nieuwe machines of hostnamen.

---

## 2. Wat je nodig hebt vóór je begint

- Toegang tot **cp-01**, **node-01**, **node-02** (SSH, liefst vanaf jumpbox).
- Repo **homelab** op de jumpbox (en eventueel op cp-01 voor `kubectl apply`-commando’s, of je kopieert kubeconfig en runt alles vanaf jumpbox).
- **Documentatie van de huidige staat** (optioneel maar handig): welke Secrets bestaan (cert-manager Cloudflare-token, etc.), welk EXTERNAL-IP de Gateway had, welke DNS-records je gebruikt.
- Een **korte onderhoudsruimte** waarin niemand van het cluster afhankelijk is.

**Kubeconfig en certs op de jumpbox:** De huidige kubeconfig op de jumpbox bevat clientcertificaten van het Hard Way-cluster. Na `kubeadm init` heeft de API-server **nieuwe** certs; de oude clientcertificaten worden niet geaccepteerd. Je moet dus de **nieuwe** admin.conf van cp-01 gebruiken (het post-bootstrap playbook haalt die op). De Let's Encrypt / Gateway-certificaten (`*.westerweel.work`) stonden als Secrets **in** het oude cluster; na het uitzetten zijn die weg. In het nieuwe cluster vraagt cert-manager ze opnieuw aan (DNS-01). Wil je het oude Gateway-cert hergebruiken, exporteer dan vóór Fase B het Secret `westerweel-work-tls` uit `gateway-system` en importeer het na de migratie in het nieuwe cluster (optioneel; meestal is opnieuw aanvragen eenvoudiger).

---

## 3. Overzicht volgorde

| Fase | Wat |
|------|-----|
| A | Huidige staat vastleggen + (optioneel) backup |
| B | Hard Way-cluster stoppen op alle nodes |
| C | kubeadm + kubelet + kubectl installeren op alle nodes |
| D | kubeadm init op cp-01 (zelfde pod/service CIDR als nu) |
| E | kubeadm join op node-01 en node-02 |
| F | Cilium installeren (CNI, Gateway API, zelfde values) |
| G | Gateway API CRDs toepassen |
| H | MetalLB (controller + speaker + IP-pool) |
| I | cert-manager (Helm) + ClusterIssuer + Secret (Cloudflare-token) |
| J | Gateway-stack: namespace, Certificate, Gateway, test-app, HTTPRoute |
| K | Kubeconfig op jumpbox; DNS/port-forward controleren |
| L | Verificatie (o.a. `curl https://test.westerweel.work`) |

---

## 3b. Automatisering met Ansible (optioneel)

Een deel van de stappen kun je met Ansible doen; de rest (Cilium, MetalLB, cert-manager, Gateway) voer je daarna vanaf de jumpbox uit met `kubectl` en `helm` (zelfde als handmatig).

**Playbooks (vanaf jumpbox, in `ansible/`):**

| Playbook | Wat het doet | Wanneer |
|----------|----------------|--------|
| `playbooks/kubeadm-install-packages.yml` | Installeert kubeadm, kubelet, kubectl op **alle** nodes (apt, Debian/Ubuntu) | Na Fase B; vervangt Fase C |
| `playbooks/kubeadm-bootstrap.yml` | `kubeadm init` op cp-01 (als nog niet gedaan), daarna `kubeadm join` op workers | Na packages; vervangt Fase D + E |

**Vereisten:** Inventory `ansible/inventory/hosts.yml` (control_plane + workers), SSH vanaf jumpbox. Variabelen (versie, endpoint, CIDRs) staan in `ansible/group_vars/k8s_cluster.yml`. Cluster-nodes en jumpbox zijn **Ubuntu** (apt); Alma is je workstation, geen cluster-node.

**Korte volgorde (vanaf jumpbox):**

1. `git pull` (repo met playbooks up-to-date).
2. **Fase B** handmatig: Hard Way overal uitzetten (systemd stop/disable op cp-01 en alle nodes).
3. `ansible-playbook playbooks/kubeadm-install-packages.yml` → packages op alle nodes (Fase C).
4. `ansible-playbook playbooks/kubeadm-bootstrap.yml` → kubeadm init op cp-01 + join op workers (Fase D + E).
5. `ansible-playbook playbooks/kubeadm-post-bootstrap.yml` → Fase F t/m K: kubeconfig ophalen, Cilium, Gateway CRDs, MetalLB, cert-manager, Gateway-stack. Optioneel Cloudflare-token meegeven: `-e "cert_manager_cloudflare_token=JOUW_TOKEN"`.
6. **Fase L** (verificatie): Certificate wachten tot Ready, DNS A-record zetten, `curl -v https://test.westerweel.work`.

Dus: **Hard Way uit → install-packages → bootstrap → post-bootstrap**; alleen Fase B en (optioneel) het Cloudflare-secret zijn handmatig.

---

## 3c. Build log bij handmatige uitrol

Als je de migratie **handmatig** uitvoert, kun je per fase noteren wat je gedaan hebt en wat de output was. Daarmee is de migratie later herhaalbaar of door iemand anders te volgen.

**Template:** [BUILDLOG-migratie-kubeadm.md](BUILDLOG-migratie-kubeadm.md) – vul per fase (A–L) datum, commando’s en resultaat in.

---

## 4. Fase A – Huidige staat vastleggen (optioneel)

Vanaf de **jumpbox** (met werkend cluster):

```bash
# Welke namespaces en wat draait daar
kubectl get ns
kubectl get pods -A -o wide

# Welke Secrets (niet de inhoud, wel de namen) – o.a. cert-manager
kubectl get secrets -A | grep -E 'cert-manager|gateway'

# Gateway EXTERNAL-IP (voor DNS)
kubectl get svc -n gateway-system
```

Noteer het **EXTERNAL-IP** van de Gateway (bijv. 192.168.178.220); dat gebruik je na de migratie weer voor DNS en port-forward. Secrets (zoals het Cloudflare-token) maak je in het nieuwe cluster opnieuw aan; ze staan niet in Git.

---

## 5. Fase B – Hard Way-cluster stoppen

Op **elke node** (cp-01, node-01, node-02) moet de kubelet stoppen. Op **cp-01** moeten daarnaast de control plane-componenten stoppen.

**Op cp-01:**

```bash
# Control plane (volgorde: eerst API-server, dan scheduler/controller-manager, dan etcd)
sudo systemctl stop kube-apiserver kube-controller-manager kube-scheduler
sudo systemctl stop etcd

# Kubelet
sudo systemctl stop kubelet

# Optioneel: uitschakelen zodat ze niet bij reboot starten
sudo systemctl disable kube-apiserver kube-controller-manager kube-scheduler etcd kubelet
```

**Op node-01 en node-02:**

```bash
sudo systemctl stop kubelet
sudo systemctl disable kubelet
```

**Optioneel – schone lei (pas toe als je zeker weet dat je geen oude data nodig hebt):**

Op **cp-01**:

```bash
sudo rm -rf /etc/kubernetes /var/lib/etcd /var/lib/kubelet
```

Op **node-01 en node-02**:

```bash
sudo rm -rf /etc/kubernetes /var/lib/kubelet
```

(Laat `/var/lib/containerd` staan; container-images kunnen hergebruikt worden.)

---

## 6. Fase C – kubeadm, kubelet, kubectl installeren (alle nodes)

Op **alle drie** de nodes (cp-01, node-01, node-02) dezelfde packages. Gebruik dezelfde **Kubernetes-versie** als je nu hebt (bijv. 1.29.x); onderstaand voor 1.29.

**Op elke node:**

```bash
# Package repo (voorbeeld: AlmaLinux/RHEL-family)
sudo curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
# OF voor RHEL/CentOS/Alma:
# sudo dnf install -y https://pkgs.k8s.io/core/stable/v1.29/rpm/el9/x86_64/kubelet-1.29.x-1.x86_64.rpm ...

# Eenvoudiger: officiële Kubernetes repo (pas versie aan indien nodig)
# Debian/Ubuntu:
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

# OF Alma/RHEL 9:
sudo dnf install -y kubelet kubeadm kubectl
sudo dnf mark hold kubelet kubeadm kubectl
```

Containerd wordt hergebruikt; die hoef je niet opnieuw te installeren. Zorg dat **kubelet** nog niet start tot na `kubeadm init`/`join` (kubeadm regelt dat).

---

## 7. Fase D – kubeadm init op cp-01

**Alleen op cp-01.** We gebruiken de **zelfde** pod- en service-CIDR als het Hard Way-cluster, zodat bestaande Cilium-values en documentatie blijven kloppen (zie [02-network.md](02-network.md)).

```bash
sudo kubeadm init \
  --control-plane-endpoint 192.168.178.201:6443 \
  --pod-network-cidr 10.200.0.0/16 \
  --service-cidr 10.32.0.0/24
```

- **control-plane-endpoint:** Hetzelfde IP als nu (cp-01), poort 6443.
- **pod-network-cidr:** 10.200.0.0/16 (zoals in Cilium `clusterPoolIPv4PodCIDRList`).
- **service-cidr:** 10.32.0.0/24 (cluster DNS wordt dan weer 10.32.0.10).

Na succes staat er een regel zoals:

```text
kubeadm join 192.168.178.201:6443 --token ... --discovery-token-ca-cert-hash sha256:...
```

**Bewaar die regel** (of de volledige output) voor de workers. Plak ook de regels voor **control plane join** als je later cp-02/cp-03 zou toevoegen; voor nu alleen de **worker**-regel gebruiken voor node-01 en node-02.

Kubeconfig voor de admin gebruiker:

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

Op cp-01 kun je nu al `kubectl get nodes` doen (alleen cp-01, status NotReady tot CNI er is).

---

## 8. Fase E – kubeadm join op node-01 en node-02

Op **node-01** en **node-02** (elk apart):

```bash
sudo kubeadm join 192.168.178.201:6443 --token <TOKEN> --discovery-token-ca-cert-hash sha256:<HASH>
```

Vervang `<TOKEN>` en `<HASH>` door de waarden uit de `kubeadm init`-output. Als de token verlopen is, genereer op cp-01 een nieuwe:

```bash
kubeadm token create --print-join-command
```

Daarna op cp-01 (of vanaf jumpbox zodra kubeconfig daar staat):

```bash
kubectl get nodes
```

Alle drie de nodes moeten verschijnen; ze blijven **NotReady** tot Cilium (CNI) is geïnstalleerd.

---

## 9. Fase F – Cilium installeren

Cilium is de CNI en zorgt voor pod-networking en (met onze values) voor de Gateway API. We gebruiken de **bestaande** values uit de repo; die matchen de gekozen pod CIDR (10.200.0.0/16).

**Vanaf de jumpbox** (of cp-01), in de **homelab repo root**:

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update

helm upgrade --install cilium cilium/cilium \
  --namespace kube-system \
  -f cluster-config/infra/cilium/values.yaml
```

Wacht tot Cilium-pods op alle nodes Running zijn:

```bash
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
```

Daarna moeten de nodes **Ready** zijn:

```bash
kubectl get nodes
```

Kubeadm heeft **CoreDNS** al geïnstalleerd; die krijgt een ClusterIP in 10.32.0.0/24 (bijv. 10.32.0.10). De extra CoreDNS-manifests uit `kubernetes/infrastructure/coredns/` zijn voor kubeadm **niet** nodig; je kunt die overslaan.

---

## 10. Fase G – Gateway API CRDs

Zonder deze CRDs kan de Cilium Gateway controller geen Gateway/HTTPRoute afhandelen. Zie [21-gateway-api-crds.md](21-gateway-api-crds.md) voor de juiste versie (compatibel met Cilium 1.19).

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml
```

Controle:

```bash
kubectl get crd | grep gateway.networking.k8s.io
```

---

## 11. Fase H – MetalLB

**Controller + speaker (upstream manifest):**

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml
```

Wacht tot pods in `metallb-system` Running zijn:

```bash
kubectl get pods -n metallb-system -w
```

**IP-pool en L2 (onze config):**

```bash
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
```

Als je een **webhook-timeout** ziet (zoals eerder op Hard Way), tijdelijk de MetalLB-validating webhooks verwijderen en daarna de pool opnieuw toepassen:

```bash
kubectl get validatingwebhookconfiguration -o name | grep metallb | xargs -r kubectl delete
kubectl apply -f kubernetes/infrastructure/metallb/ip-pool.yaml
```

---

## 12. Fase I – cert-manager + ClusterIssuer + Secret

**Helm install met values uit repo:**

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  -f kubernetes/infrastructure/cert-manager/values.yaml
```

Wacht tot pods in `cert-manager` Running zijn:

```bash
kubectl get pods -n cert-manager -w
```

**Cloudflare-token Secret** (niet in Git; handmatig opnieuw aanmaken):

```bash
kubectl create secret generic cloudflare-api-token \
  --from-literal=api-token=JOUW_CLOUDFLARE_TOKEN \
  --namespace cert-manager
```

**ClusterIssuer (prod):** Pas in `kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml` het e-mailadres aan en apply:

```bash
kubectl apply -f kubernetes/infrastructure/cert-manager/cluster-issuer-prod.yaml
```

Bij webhook-timeout (cert-manager): zie [24-cert-manager.md](24-cert-manager.md) (tijdelijk webhooks verwijderen, Certificate opnieuw aanmaken).

---

## 13. Fase J – Gateway-stack (namespace, Certificate, Gateway, test-app, HTTPRoute)

Alles in de volgorde zoals in [25-gateway-tls.md](25-gateway-tls.md). **Vanaf repo root:**

```bash
# Namespace
kubectl apply -f kubernetes/infrastructure/gateway/namespace.yaml

# Certificate (cert-manager vraagt dan wildcard aan)
kubectl apply -f kubernetes/infrastructure/gateway/certificate.yaml
kubectl get certificate -n gateway-system -w
# Wacht tot Ready=True

# Gateway
kubectl apply -f kubernetes/infrastructure/gateway/gateway.yaml

# LoadBalancer-IP noteren
kubectl get svc -n gateway-system
# Noteer EXTERNAL-IP (bijv. 192.168.178.220)

# Test-app + HTTPRoute
kubectl apply -f kubernetes/infrastructure/gateway/gateway-test-app.yaml
kubectl apply -f kubernetes/infrastructure/gateway/httproute-test.yaml
```

**DNS:** Zorg dat **test.westerweel.work** naar het EXTERNAL-IP van de Gateway wijst (A-record in Cloudflare of lokaal /etc/hosts). Het IP is vaak hetzelfde als vóór de migratie (zelfde MetalLB-pool).

**Port-forward (optioneel):** Op je router 443 → EXTERNAL-IP (bijv. 192.168.178.220) als je vanaf internet wilt bereiken.

---

## 14. Fase K – Kubeconfig op jumpbox

Zodat je vanaf de **jumpbox** met het nieuwe cluster werkt (zelfde hosts,zelfde endpoint):

**Op cp-01:** Admin-kubeconfig staat in `/etc/kubernetes/admin.conf`. Kopieer die naar de jumpbox:

```bash
# Vanaf jumpbox (SSH naar cp-01 en kopieer, of scp vanaf cp-01)
scp cp-01:/etc/kubernetes/admin.conf ~/.kube/config
# Of: ssh cp-01 "cat /etc/kubernetes/admin.conf" > ~/.kube/config
```

Pas eventueel het **server-adres** in `~/.kube/config` aan als er een andere hostnaam in staat (bijv. `https://192.168.178.201:6443`), zodat je vanaf de jumpbox hetzelfde IP gebruikt als voorheen.

Daarna vanaf de jumpbox:

```bash
kubectl get nodes
kubectl get pods -A
```

---

## 15. Fase L – Verificatie

- **Nodes:** `kubectl get nodes` → alle drie Ready.
- **Pods:** Cilium, CoreDNS (kube-dns), MetalLB, cert-manager, gateway-system (Cilium Gateway pods, echo-test) Running.
- **Gateway:** `kubectl get gateway -n gateway-system` → listener klaar.
- **HTTPS-test (vanaf Alma of machine met DNS):**

  ```bash
  curl -v https://test.westerweel.work
  ```

  Je moet geldig TLS (Let's Encrypt) en de JSON-response van de echo-server zien.

Als dit lukt, is de migratie geslaagd: **zelfde hosts, zelfde jumpbox, nieuw kubeadm-cluster**; geen tweede cluster ernaast, geen wijziging van hostnamen of IP’s.

---

## 16. Samenvatting: wat blijft hetzelfde, wat is nieuw

| Item | Situatie |
|------|----------|
| Hosts | Zelfde: cp-01, node-01, node-02 |
| IP’s | Zelfde: 192.168.178.201/202/203 |
| Jumpbox | Zelfde; kubeconfig wijst weer naar 192.168.178.201:6443 |
| Pod CIDR | Zelfde: 10.200.0.0/16 (door kubeadm init) |
| Service CIDR | Zelfde: 10.32.0.0/24 |
| DNS (A-record, port-forward) | Zelfde EXTERNAL-IP gebruiken (bijv. 192.168.178.220) |
| Secrets (Cloudflare, etc.) | Opnieuw aanmaken (niet in Git) |
| Config in repo | Zelfde manifests/Helm values; opnieuw toepassen |

---

## Referenties

| Onderwerp | Link |
|-----------|------|
| Stappenplan GitOps | [20-stappenplan-gitops.md](20-stappenplan-gitops.md) |
| Netwerk / IP-schema | [02-network.md](02-network.md) |
| Gateway + TLS (stap 5) | [25-gateway-tls.md](25-gateway-tls.md) |
| cert-manager | [24-cert-manager.md](24-cert-manager.md) |
| MetalLB | [23-metallb.md](23-metallb.md) |
| kubeadm | [kubernetes.io/docs/setup](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/) |
