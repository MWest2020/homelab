# Post-installatie Hardening

Dit document beschrijft de stappen na een verse Ubuntu Server installatie, voordat we Kubernetes installeren.

> **Tip**: Deze stappen zijn geautomatiseerd in `ansible/playbooks/prepare-nodes.yml`. 
> Zie [Ansible Setup](05-ansible.md) voor het automatisch uitvoeren.

## Handmatige Stappen (eerste keer)

De eerste keer doe je dit handmatig om te begrijpen wat er gebeurt. Daarna altijd via Ansible.

### 1. System Update

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Intel Microcode (Security Patches)

```bash
sudo apt install intel-microcode -y
```

> Belangrijk voor HP EliteDesk's met Intel CPU's - patcht CPU vulnerabilities

### 3. Essentiële Packages

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    htop \
    net-tools \
    vim \
    unzip
```

### 4. SSH Key Setup

**Op je lokale machine (Windows/WSL):**
```bash
# Genereer key als je die nog niet hebt
ssh-keygen -t ed25519 -C "homelab"

# Kopieer naar alle nodes
ssh-copy-id admin@192.168.178.201
ssh-copy-id admin@192.168.178.202
ssh-copy-id admin@192.168.178.203
```

### 5. SSH Hardening

**Op elke node:**
```bash
sudo vim /etc/ssh/sshd_config
```

Wijzig/voeg toe:
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

> ⚠️ Test SSH key login in een NIEUWE terminal voordat je de huidige sluit!

### 6. Firewall Basis

```bash
sudo ufw allow ssh
sudo ufw allow 6443/tcp  # Kubernetes API
sudo ufw enable
```

### 7. Hostname Verificatie

```bash
hostnamectl
```

Moet tonen: `cp-01`, `node-01`, of `node-02`

### 8. Disable Swap (vereist voor Kubernetes)

```bash
sudo swapoff -a
sudo sed -i '/swap/d' /etc/fstab
```

Verify:
```bash
free -h  # Swap moet 0 zijn
```

### 9. Kernel Modules voor Kubernetes

```bash
# Load modules
sudo modprobe overlay
sudo modprobe br_netfilter

# Persist on reboot
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

# Sysctl settings
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sudo sysctl --system
```

### 10. Hosts File (cluster discovery)

```bash
sudo tee -a /etc/hosts <<EOF
192.168.178.201 cp-01
192.168.178.202 node-01
192.168.178.203 node-02
EOF
```

## Verificatie Checklist

Na deze stappen op alle nodes:

- [ ] `ssh admin@cp-01` werkt met key (geen wachtwoord)
- [ ] `ssh admin@node-01` werkt met key
- [ ] `ssh admin@node-02` werkt met key
- [ ] `sudo` werkt op alle nodes
- [ ] Alle nodes kunnen elkaar pingen (`ping node-01` vanaf cp-01)
- [ ] Alle nodes kunnen internet bereiken (`ping 8.8.8.8`)
- [ ] Swap is uitgeschakeld (`free -h` toont 0 swap)
- [ ] Kernel modules geladen (`lsmod | grep br_netfilter`)

## Automatiseren met Ansible

Nu je begrijpt wat er gebeurt, hoef je dit nooit meer handmatig te doen:

```bash
cd ansible
ansible-playbook playbooks/prepare-nodes.yml
```

Dit playbook doet alle bovenstaande stappen automatisch op alle nodes.

## Volgende Stap

Nodes zijn klaar voor Kubernetes. Zie [Kubernetes Setup](06-kubernetes.md).
