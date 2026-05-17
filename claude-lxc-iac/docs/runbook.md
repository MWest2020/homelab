# Runbook — agent-lxc

Operational doc for the Claude Code dev container. Every step has expected output / next-action notes so it can be executed without rereading the design.

All commands run from **jumpy** unless explicitly noted. The IaC lives under `~/homelab/claude-lxc-iac/` on jumpy (subfolder of the main homelab repo).

---

## 0. Pre-flight (one-off per Proxmox host / per token rotation)

### 0.1 Create the API token on Proxmox

In the Proxmox web UI: Datacenter → Permissions → API Tokens → Add.
- User: `terraform@pve`
- Token ID: `automation-lxc`
- Privilege Separation: **off** (token inherits user perms — operator can flip back on if they later attach role ACL to the token separately)
- Save the secret to the password manager and to jumpy's env shell:

```bash
# on jumpy
echo 'export PROXMOX_VE_API_TOKEN="terraform@pve!automation-lxc=<secret>"' >> ~/.bashrc
source ~/.bashrc
```

If you prefer privilege-separation on the token, also run on Proxmox:
```bash
pveum aclmod / -token 'terraform@pve!automation-lxc' -role TerraformProv
```
Make sure the parent user `terraform@pve` already has TerraformProv too (see `homelab/docs/07-vm-provisioning-stack.md`).

### 0.2 Download the Ubuntu LXC template

```bash
ssh root@192.168.178.10 'pveam list local | grep ubuntu-24.04'
# if not present:
ssh root@192.168.178.10 'pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst'
```

### 0.3 Mint a Tailscale auth key

Browser: https://login.tailscale.com/admin/settings/keys → Generate auth key.
- Reusable: **off**
- Ephemeral: **off**
- Tags: `tag:homelab-router` (tag-approval is automatic via your existing `tagOwners` policy — no separate "Pre-approved" toggle in current Tailscale UI)
- Description: `agent-lxc bootstrap YYYY-MM-DD`
- Validity: 1 day (it's used once)

Copy the key (`tskey-auth-...`); paste into `ansible/vault/secrets.yml` (next step).

### 0.4 Prepare the Ansible vault

```bash
# on jumpy, in the repo
cp ansible/vault/secrets.yml.example ansible/vault/secrets.yml
# edit secrets.yml, paste in the tskey-... above
vim ansible/vault/secrets.yml

# pick a strong vault password and stash it
openssl rand -base64 32 > ~/.vault_pass
chmod 600 ~/.vault_pass

# encrypt the secrets file
ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass ansible-vault encrypt ansible/vault/secrets.yml

# verify it decrypts
ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass ansible-vault view ansible/vault/secrets.yml

# export for the rest of the session
export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass
```

### 0.5 Configure inventory + group_vars

```bash
cp ansible/inventory.yml.example ansible/inventory.yml
cp ansible/group_vars/claude_dev.yml.example ansible/group_vars/claude_dev.yml
# edit ansible_host to the static IP planned (default 192.168.178.58)
# edit dev_user_authorized_keys to include your SSH pubkey
```

### 0.6 Configure tfvars

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# fill in static_ip (required), gateway, cidr — see comments in the file
```

---

## 1. Initial provision

### 1.1 Terraform

```bash
cd terraform
terraform init                          # downloads bpg/proxmox + random providers
TF_LOG=DEBUG terraform apply 2>&1 | tee /tmp/agent-lxc-tf.log
```

Expected: `Apply complete! Resources: 2 added` (LXC + random_password). Output block prints:
- `container_id = 210`
- `assigned_ip = 192.168.178.58`
- `next_steps` (multi-line with the playbook command)
- `root_initial_password = <sensitive>`

If the apply hangs >5 minutes on "Still creating", check `TF_LOG`'s most recent HTTP responses for 403's — token permissions are the usual culprit. See `homelab/memory/project_proxmox_terraform_token_perms.md`.

### 1.2 Ansible

```bash
cd ../ansible
ansible-galaxy collection install -r requirements.yml    # one-off
ansible-playbook -i inventory.yml playbook.yml -vv 2>&1 | tee /tmp/agent-lxc-ansible.log
```

Expected: `failed=0 unreachable=0` for `agent-lxc`. Runtime ~3-5 min on the first build (apt update + tailscale install + npm install dominate).

At the end, the playbook prints:
- Claude Code version
- GitHub SSH public key (copy-paste target for github.com/settings/keys)

---

## 2. Interactive one-offs after first run

### 2.1 Claude Code account login

```bash
ssh agent@192.168.178.58    # or `ssh agent@agent-lxc` once Tailscale is up
claude
```

The first invocation of `claude` walks you through Anthropic account auth. On headless systems it falls back from browser to copy-paste URL — open the URL on your laptop, complete auth, paste the resulting code back.

### 2.2 Add the GitHub SSH key

The Ansible run prints the key. Otherwise:

```bash
ssh agent@agent-lxc 'cat ~/.ssh/id_ed25519_github.pub'
```

Add at https://github.com/settings/keys:
- Title: `agent-lxc`
- Scope: **Authentication and Signing**
- Do **not** enable for SSO of any organisation other than your own MWest2020 account.

Test:
```bash
ssh agent@agent-lxc 'ssh -T git@github.com'
# expected: "Hi mwest2020! You've successfully authenticated, but GitHub does not provide shell access."
```

---

## 3. Day-2 workflow

### 3.1 Connect (any device)

```bash
ssh agent@agent-lxc                    # via Tailscale (any tailnet device) or LAN (jumpy)
tmux new -A -s main                    # attach-or-create the main session
claude                                 # start Claude Code
```

Inside tmux: `Ctrl-b d` detach (sessie blijft draaien), `tmux a` reattach later. Work survives SSH disconnection.

### 3.2 Multi-device shared sessions

`agent-lxc` is één machine met één tmux-server per user. Meerdere clients kunnen aan dezelfde session attachen — desktop, jumpy, mobiel (Terminus), tablet. Allemaal zien hetzelfde scherm realtime.

```bash
# Desktop, eerste keer
ssh agent@agent-lxc
tmux new -A -s main

# Mobiel (Terminus), later — attach aan dezelfde main
ssh agent@agent-lxc
tmux a -t main
```

Wat je op mobiel typt, ziet desktop direct. `Ctrl-b d` op één client = detach, andere clients blijven verbonden.

Voor losse parallelle sessies (niet shared, wel persistent):
```bash
tmux new -A -s work       # bv. coding
tmux new -A -s monitor    # bv. logs / tail
tmux ls                   # alle sessies tonen
tmux a -t monitor         # switch
```

### 3.3 Mobile setup (Terminus iOS/Android)

1. Tailscale-app installen + inloggen met MWest2020-account → mobiel zit in tailnet, ziet `agent-lxc` als `100.x.x.x`
2. Terminus: Settings → Keychain → New Key → ed25519 → Generate (private key blijft in Terminus' keychain)
3. Exporteer pubkey, voeg toe als nieuwe entry in `ansible/group_vars/claude_dev.yml` `dev_user_authorized_keys` met label (bv. `terminus-iphone`)
4. Re-run alleen base-rol: `ansible-playbook -i inventory.yml playbook.yml --tags base`
5. In Terminus host config: Host = `100.x.x.x` (uit Tailscale admin → Machines → agent-lxc), User = `agent`, Identity = Terminus-keypair

Per-device pubkeys voor mobiel = wél zinvol — mobiele apparaten hebben ander threat-model dan jumpy/alma (verlies/diefstal). Eén label per device in `authorized_keys` voor snelle revocation als nodig.

### 3.4 Waar leeft de code

Code-tree leeft op **`agent-lxc`** filesystem (typisch `/home/agent/repos/<project>/`). Niet op node-01 (= k8s worker), niet op jumpy, niet op alma. Multi-device-access werkt omdat alle devices SSH'en naar dezelfde LXC en dus dezelfde files zien.

Wil je vanuit `agent-lxc` werken aan iets dat *elders* leeft (bv. k8s manifests op jumpy), dan clone je dat repo binnen `agent-lxc` of mount je 't via SSHFS. Maar daadwerkelijke code-editing happens on agent-lxc.

---

## 4. Re-running

### 4.1 Safe re-runs (idempotent)

```bash
cd terraform && terraform apply         # should report 0 to add / 0 to change
cd ../ansible && ansible-playbook -i inventory.yml playbook.yml
```

Both should show no changes on a converged container.

### 4.2 Tagged role re-runs

After tweaking a single role:

```bash
ansible-playbook -i inventory.yml playbook.yml --tags nodejs
```

Available tags: `base`, `ssh_hardening`, `tailscale`, `nodejs`, `claude_code`, `github_identity`.

### 4.3 Renewing the Tailscale session

If the device gets disconnected from Tailscale (key expiry, manual remove from admin):

```bash
# new auth key first, update vault
ansible-vault edit ansible/vault/secrets.yml

# re-run only the tailscale role
ansible-playbook -i inventory.yml playbook.yml --tags tailscale
```

The `tailscale up` task only runs when `tailscale status` reports something other than `Running`, so this is safe to re-run on healthy containers (no-op).

---

## 5. Destroy / recreate

```bash
cd terraform
terraform destroy        # confirm with 'yes'
```

This stops and removes the LXC (id 210). Tailscale node entry for `agent-lxc` lingers in the admin console — remove it manually under Machines → agent-lxc → `...` → Remove.

Recreate: full `terraform apply` → **§ 6.1 one-off (`pct set ... -dev0 /dev/net/tun`)** → `ansible-playbook` from step 1. The tun-device step is required on every fresh provision because terraform can't set it via API token.

---

## 6. Troubleshooting (top 5)

| Symptom | Diagnosis | Fix |
|---|---|---|
| `terraform apply` hangs at "Still creating" | Token lacks `VM.Audit` etc. — bpg polls 403 | See `homelab/memory/project_proxmox_terraform_token_perms.md`; ensure both user and token have TerraformProv on `/` |
| LXC starts but no IPv4 ("incomplete" in arp from outside) | Missed `static_ip` config or wrong CIDR/gateway | `pct config 210 \| grep net0` on Proxmox; `pct exec 210 -- ip a` |
| Tailscale role: `Permission denied (publickey)` from auth-key task | Auth key revoked / wrong tag / not pre-approved | Mint a new key in admin, update vault, re-run with `--tags tailscale` |
| Ansible: `command not found: claude` for the verify step | `~/.npm-global/bin` not on PATH for the running session | The role sets PATH via `environment:`; if you also touched `.bashrc`, source it or restart shell |
| SSH refuses `agent@agent-lxc` after ssh_hardening | Hardening reloaded sshd but `dev_user_authorized_keys` was empty | Recover via Proxmox console (`pct enter 210`), fix authorized_keys, re-run `--tags base,ssh_hardening` |

### 6.1 `/dev/net/tun` passthrough — mandatory one-off after every terraform apply

Proxmox **only allows `root@pam`** to configure device-passthrough; API tokens (even with full TerraformProv role) get 403. We removed the `device_passthrough` block from `main.tf` (see ADR-007 for the full explanation of why); after every fresh `terraform apply` you must add the tun device manually:

```bash
ssh root@192.168.178.10 'pct set 210 -dev0 /dev/net/tun && pct reboot 210'
```

Verify inside the LXC:
```bash
ssh root@192.168.178.10 'pct exec 210 -- ls -l /dev/net/tun'
# expected: crw-rw-rw- 1 nobody nogroup 10, 200 ... /dev/net/tun
```

The `nobody:nogroup` ownership is normal in an unprivileged LXC — the host doesn't know the remapped UID by name. File mode `rw` for all means `tailscaled` in the container can use it.

**Why this is a one-off, not a recurring task**: Proxmox writes `dev0: /dev/net/tun` to `/etc/pve/lxc/210.conf` and that persists across reboots. Only a fresh `terraform destroy && terraform apply` cycle wipes the config and requires re-running the `pct set`. The runbook's destroy section reminds you of this.

See `docs/decisions.md` ADR-007 for: what `/dev/net/tun` actually is, why LXC blocks devices, why Proxmox restricts passthrough to root@pam, and rejected alternatives (privileged LXC, userspace-mode Tailscale, terraform-as-root@pam).

---

## 7. Backups (out of scope here, but…)

This repo does not configure backups. Use Proxmox's `vzdump` against LXC 210 on a schedule. Recommended retention: 7 daily + 4 weekly snapshots to a separate datastore. Configure once in the Proxmox UI under Datacenter → Backup.
