# Netwerk Configuratie

## IP Schema

> **Note**: Echte IP's staan in `.env`. Zie `.env.example` voor template.

| Device | Hostname | IP Adres | Rol |
|--------|----------|----------|-----|
| Router | - | `<GATEWAY_IP>` | Gateway |
| Control Plane | cp-01 | `<CONTROL_PLANE_IP>` | K8s Control Plane (etcd, apiserver, scheduler, controller-manager) |
| Worker 1 | node-01 | `<WORKER_01_IP>` | K8s Worker (kubelet, containerd) |
| Worker 2 | node-02 | `<WORKER_02_IP>` | K8s Worker (kubelet, containerd) |
| Jumpbox | localhost | DHCP | Management (kubectl, ansible, ssh) |

## Netwerk Settings

```
Subnet:      <NETWORK_SUBNET>
Gateway:     <GATEWAY_IP>
DNS:         1.1.1.1, 8.8.8.8
```

## Kubernetes Netwerk Ranges (gereserveerd)

```
Pod CIDR:     10.200.0.0/16   (Kubernetes the Hard Way)
Service CIDR: 10.32.0.0/24    (Kubernetes the Hard Way)
Cluster DNS:  10.32.0.10
```

> Deze ranges komen uit Kelsey Hightower's "Kubernetes the Hard Way" tutorial.

## Poorten

| Poort | Protocol | Gebruik |
|-------|----------|---------|
| 22 | TCP | SSH |
| 6443 | TCP | Kubernetes API |
| 80 | TCP | HTTP (Ingress) |
| 443 | TCP | HTTPS (Ingress) |
| 10250 | TCP | Kubelet API |

## Diagram

```
                         Internet
                             │
                        [Router]
                      <GATEWAY_IP>
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
[Jumpbox]                    │                        │
 (DHCP)                      │                        │
    │              ┌─────────┴─────────┐              │
    │              │                   │              │
    └──────► [cp-01]              [node-01]      [node-02]
   kubectl   <CP_IP>              <W1_IP>        <W2_IP>
   ansible   Control Plane          Worker         Worker
             etcd, apiserver       kubelet        kubelet
             scheduler, cm         containerd     containerd
```

## Beslissingen

### Waarom statische IP's?
- Kubernetes vereist stabiele IP's voor cluster communicatie
- Maakt Ansible inventory simpeler
- Voorkomt issues bij DHCP lease renewal

### Waarom Cloudflare + Google DNS?
- Redundantie (twee providers)
- Snelle response times
- Geen ISP DNS tracking
