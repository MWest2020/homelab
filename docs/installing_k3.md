This document installs a **high‑availability k3s cluster** with **3 control‑planes** (embedded etcd, default flannel), with *no ingress controller just yet. It assumes your networking, 
SSH keys, and basic hardening are complete.

## Topology

- Nodes:
  - **node1** → `[NODE1_IP]` (bootstrap server)
  - **node2** → `[NODE2_IP]` (server)
  - **node3** → `[NODE3_IP]` (server)
- LAN subnet used in examples: **`[LAN_CIDR]`** (e.g. `192.168.178.0/24`)

## 0) UFW — allow intra‑cluster traffic (on **all three** nodes)

> Keep everything **LAN‑only**. Do **not** expose 6443 to the internet.

```bash
# SSH (management)
sudo ufw allow from [LAN_CIDR] to any port 22 proto tcp

# Kubernetes common ports (all nodes)
sudo ufw allow from [LAN_CIDR] to any port 10250 proto tcp   # kubelet
sudo ufw allow from [LAN_CIDR] to any port 8472 proto udp    # flannel VXLAN

# Control‑plane only (all 3 servers here)
sudo ufw allow from [LAN_CIDR] to any port 6443 proto tcp    # kube‑apiserver
sudo ufw allow from [LAN_CIDR] to any port 2379:2380 proto tcp  # etcd peer/client

sudo ufw status
```

## 1) Bootstrap the cluster on **node1** (Traefik OFF)

```bash
ssh [NODE1_USER]@[NODE1_IP]
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --cluster-init --disable traefik" sh -
sudo systemctl status k3s --no-pager
sudo cat /var/lib/rancher/k3s/server/node-token
# copy the full K10...::server:... token that is printed (store as [K3S_NODE_TOKEN])
exit
```

## 2) Join **node2** and **node3** as servers

> Replace placeholders with your values:
> - `[K3S_NODE_TOKEN]` → the full `K10...::server:...` string from node1
> - `[SERVER_IP]` → `https://[NODE1_IP]:6443`

```bash
# node2
ssh [NODE2_USER]@[NODE2_IP]
export TOKEN="[K3S_NODE_TOKEN]"
export SERVER="https://[NODE1_IP]:6443"
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --server $SERVER --token $TOKEN --disable traefik" sh -
sudo systemctl status k3s --no-pager
exit

# node3
ssh [NODE3_USER]@[NODE3_IP]
export TOKEN="[K3S_NODE_TOKEN]"
export SERVER="https://[NODE1_IP]:6443"
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --server $SERVER --token $TOKEN --disable traefik" sh -
sudo systemctl status k3s --no-pager
exit
```

## 3) Verify from **node1**

```bash
ssh [NODE1_USER]@[NODE1_IP]
kubectl get nodes -o wide
kubectl -n kube-system get pods -o wide
exit
```
All three nodes should become **Ready** (first time: ~1–3 minutes).

## 4) Use kubectl from your laptop (keep work kubeconfig untouched)

Place the homelab kubeconfig in a dedicated folder (e.g. on your E: drive) and pass it explicitly to kubectl.

```bash
# On your laptop
mkdir -p [PATH]/.kube

# Copy kubeconfig safely from node1:
ssh -t [NODE1_ALIAS_OR_USER]@[NODE1_IP] 'sudo install -m 644 /etc/rancher/k3s/k3s.yaml /tmp/k3s.yaml'
scp [NODE1_ALIAS_OR_USER]@[NODE1_IP]:/tmp/k3s.yaml [PATH]/.kube/homelab.yaml
ssh [NODE1_ALIAS_OR_USER]@[NODE1_IP] 'sudo rm -f /tmp/k3s.yaml'

# Replace loopback with node1 LAN IP
sed -i 's/127\.0\.0\.1/[NODE1_IP]/' [PATH]/.kube/homelab.yaml

# Test (explicit kubeconfig)
kubectl --kubeconfig [PATH]/.kube/homelab.yaml cluster-info
kubectl --kubeconfig [PATH]/.kube/homelab.yaml get nodes -o wide
```

> Optional (later): add `--write-kubeconfig-mode 644` to the k3s service if you want non‑root read access on the node. The copy method above is safer and sufficient for a homelab.

## 5) Quick smoke test (no ingress yet)

```bash
kubectl --kubeconfig [PATH]/.kube/homelab.yaml create deployment hello --image=nginx
kubectl --kubeconfig [PATH]/.kube/homelab.yaml expose deployment hello --type=ClusterIP --port=80
kubectl --kubeconfig [PATH]/.kube/homelab.yaml get svc,pod -o wide
```

## 6) Troubleshooting

- **Nodes NotReady** → verify UFW rules and open sockets:
  ```bash
  for h in [NODE1_IP] [NODE2_IP] [NODE3_IP]; do
    ssh [SSH_USER]@$h 'sudo ufw status | sed -n "1,40p"; ss -tulpn | egrep ":6443|:2379|:2380|:10250|:8472" || true'
  done
  ```
- **k3s logs / status**:
  ```bash
  ssh [NODE1_USER]@[NODE1_IP] 'sudo systemctl status k3s --no-pager'
  ssh [NODE1_USER]@[NODE1_IP] 'sudo journalctl -u k3s -n 200 --no-pager'
  ```
- **Uninstall (only if you need to reset)**:
  ```bash
  # on any server node you want to remove:
  sudo /usr/local/bin/k3s-uninstall.sh
  ```

## 7) What’s next?

- **README 04** will cover **MetalLB** (assign a **single** IP to ingress‑nginx) and then **ingress‑nginx** + a simple Ingress example.
- Keep kube‑API private (LAN/VPN). Do not publish 6443 to the internet.

— End —
