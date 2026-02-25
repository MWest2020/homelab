# Netwerk Configuratie

## IP Schema

| Device | Hostname | IP Adres | Rol |
|--------|----------|----------|-----|
| Router | - | 192.168.178.1 | Gateway |
| Control Plane | cp-01 | 192.168.178.201 | K8s Control Plane (etcd, apiserver, scheduler, controller-manager) |
| Worker 1 | node-01 | 192.168.178.202 | K8s Worker (kubelet, containerd) |
| Worker 2 | node-02 | 192.168.178.203 | K8s Worker (kubelet, containerd) |
| Jumpbox | jump | DHCP | Management (kubectl, ansible, ssh) |

## Netwerk Settings

```
Subnet:      192.168.178.0/24
Gateway:     192.168.178.1
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
                     192.168.178.1
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
 [jump]                      │                        │
 (DHCP)                      │                        │
    │              ┌─────────┴─────────┐              │
    │              │                   │              │
    └──────► [cp-01]              [node-01]      [node-02]
   kubectl   .178.201              .178.202       .178.203
   ansible   Control Plane          Worker         Worker
             etcd, apiserver       kubelet        kubelet
             scheduler, cm         containerd     containerd
```

## MetalLB (LoadBalancer VIPs)

| Doel | Range |
|------|-------|
| LoadBalancer Services (Gateway, etc.) | 192.168.178.220–192.168.178.230 |

**Belangrijk:** Zorg dat .220–.230 **buiten** de DHCP-range vallen van het apparaat dat bij jou DHCP doet (switch, router of anders). Anders kan MetalLB een IP uitdelen dat ook aan een client wordt gegeven → conflict.

---

## Beslissingen

### Waarom statische IP's?
- Kubernetes vereist stabiele IP's voor cluster communicatie
- Maakt Ansible inventory simpeler
- Voorkomt issues bij DHCP lease renewal

### Waarom Cloudflare + Google DNS?
- Redundantie (twee providers)
- Snelle response times
- Geen ISP DNS tracking
