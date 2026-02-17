# Ansible Setup & Gebruik

## Vereisten

Op je **lokale machine** (waar je Ansible runt):

```bash
# Windows: gebruik WSL2
wsl --install

# In WSL/Linux:
sudo apt update
sudo apt install ansible python3-pip -y

# Installeer extra collections
ansible-galaxy collection install community.general ansible.posix
```

## SSH Keys Configureren

Voordat Ansible werkt, moet je SSH key-based auth hebben:

```bash
# Genereer key (als je die nog niet hebt)
ssh-keygen -t ed25519 -C "homelab"

# Kopieer naar alle nodes
ssh-copy-id admin@192.168.178.201
ssh-copy-id admin@192.168.178.202
ssh-copy-id admin@192.168.178.203

# Test verbinding
ssh admin@192.168.178.201 "hostname"
```

## Inventory

**Setup:**
```bash
cp ansible/inventory/hosts.yml.example ansible/inventory/hosts.yml
```

De nodes zijn gedefinieerd in `ansible/inventory/hosts.yml`:

```yaml
all:
  children:
    k8s_cluster:
      children:
        control_plane:
          hosts:
            cp-01:
              ansible_host: 192.168.178.201
        workers:
          hosts:
            node-01:
              ansible_host: 192.168.178.202
            node-02:
              ansible_host: 192.168.178.203
```

## Playbooks

### prepare-nodes.yml

Bereidt verse Ubuntu nodes voor op Kubernetes:

| Taak | Beschrijving |
|------|--------------|
| System updates | apt upgrade, autoremove |
| Intel microcode | CPU security patches |
| Essential packages | curl, git, htop, etc. |
| SSH hardening | Disable password auth, root login |
| UFW firewall | Allow SSH, K8s ports |
| Kernel modules | overlay, br_netfilter |
| Sysctl settings | IP forwarding, bridge netfilter |
| Disable swap | Vereist voor Kubernetes |
| Hostnames | Set hostname, update /etc/hosts |

**Gebruik:**

```bash
cd ansible

# Test eerst (dry-run)
ansible-playbook playbooks/prepare-nodes.yml --check

# Uitvoeren
ansible-playbook playbooks/prepare-nodes.yml

# Alleen op specifieke node
ansible-playbook playbooks/prepare-nodes.yml --limit cp-01
```

## Handige Commands

```bash
# Ping alle nodes
ansible all -m ping

# Run ad-hoc command
ansible all -a "uptime"

# Check OS versie
ansible all -a "cat /etc/os-release"

# Reboot alle nodes
ansible all -m reboot

# Check playbook syntax
ansible-playbook playbooks/prepare-nodes.yml --syntax-check
```

## Troubleshooting

### "Permission denied (publickey)"
SSH key niet gekopieerd. Run `ssh-copy-id` eerst met wachtwoord auth.

### "UNREACHABLE"
- Check of node aan staat
- Check IP adres in inventory
- Check firewall/netwerk

### "Missing sudo password"
Inventory heeft `ansible_become: true` maar user kan geen passwordless sudo. Fix:
```bash
# Op de node:
echo "admin ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/admin
```

## Volgende Stap

Na `prepare-nodes.yml` zijn de nodes klaar voor Kubernetes. Zie [Kubernetes Setup](06-kubernetes.md).
