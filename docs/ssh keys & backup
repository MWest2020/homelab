# Step 01 — SSH keys on the nodes + backup key

This document sets up your **admin SSH keys** on the nodes and creates a **second (backup) key** on your E‑drive. The backup key is **installed on all hosts immediately**, so if you lose your laptop you can log in with the backup.

## Prereqs
- Your laptop is on the same LAN — wired on Port 8 or Wi‑Fi behind your router/extender.
- You can **once** log in to each node with username/password.

## 1) Aliases on your laptop (optional but convenient)
Create `~/.ssh/config` (WSL/macOS/Linux) with aliases:
```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat >> ~/.ssh/config <<'EOF'
Host node1
  HostName [HOST IP]
  User [USER NAME]
  IdentityFile ~/.ssh/[filename]

Host node2
  HostName [HOST IP]
  User [USER NAME]
  IdentityFile ~/.ssh/[filename]

Host node3
  HostName [HOST IP]
  User [USER NAME]
  IdentityFile ~/.ssh/[filename]
EOF
chmod 600 ~/.ssh/config
```

## 2) Push your primary (admin) key
Create (or reuse) your **primary** key and push it to the nodes (WSL):
```bash
[ -f ~/.ssh/[filename] ] || ssh-keygen -t ed25519 -C "lab-admin"

for h in node1 node2 node3; do
  ssh-copy-id -i ~/.ssh/[filename].pub $h
done
```
> First time: accept the **host key** (`yes`) and enter the **account password**.

## 3) Generate and install the backup key (on E:\)
Use the script below. It creates a **new backup key** in `[PATH]` and **installs** the public key on all hosts.

File: `make_ssh_backup_and_install.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

BASE="[PATH]"
mkdir -p "$BASE"; chmod 700 "$BASE"

HOSTS=(
  "[USERNAME]@"[HOST IP]
  "[USERNAME]@[HOST IP]"
  "[USERNAME]@[HOST IP]"
)

KEY_NAME="[filename]_homelab_backup"
KEY_PATH="$BASE/$KEY_NAME"
TS="$(date +%Y%m%d-%H%M%S)"

BK="$BASE/backup-$TS"; mkdir -p "$BK"
[ -f "$KEY_PATH" ] && mv "$KEY_PATH" "$BK/" || true
[ -f "$KEY_PATH.pub" ] && mv "$KEY_PATH.pub" "$BK/" || true

echo ">>> Generate backup SSH key at $KEY_PATH (choose a passphrase; Enter = none):"
ssh-keygen -t ed25519 -f "$KEY_PATH" -C "homelab-backup-$(hostname)-$TS"
chmod 600 "$KEY_PATH"; chmod 644 "$KEY_PATH.pub"
PUB="$(cat "$KEY_PATH.pub")"
echo ">>> New public key:"
echo "$PUB"

for entry in "${HOSTS[@]}"; do
  user="${entry%@*}"; host="${entry#*@}"
  echo ">>> Install key on $user@$host (first time may ask for password)"
  ssh-keygen -R "$host" >/dev/null 2>&1 || true
  echo "$PUB" | ssh -o StrictHostKeyChecking=accept-new "$user@$host"     'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
  ssh -i "$KEY_PATH" -o PreferredAuthentications=publickey "$user@$host" 'echo "OK: $(hostname) - $(id -un)"'
done

echo ">>> DONE. Private key: $KEY_PATH  |  Public key: $KEY_PATH.pub"
echo ">>> Tip: copy this folder securely to your hardware stick or private repo."
```

Usage:
```bash
chmod +x make_ssh_backup_and_install.sh
./make_ssh_backup_and_install.sh
```

## 4) SSH agent (avoid re‑typing passphrase)
```bash
# in WSL
eval "$(ssh-agent -s)"
ssh-add /[PATH]/[filename]_homelab_backup
```
The agent caches your passphrase for the session.

## 5) Hardening (after successful key login)
Run on **each node**:
```bash
# SSH
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# Firewall
sudo apt -y install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```
> Later on `node1` we will open **6443/tcp** for the Kubernetes API.

