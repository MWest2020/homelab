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
- Pre-approved: **on**
- Tags: `tag:homelab-router`
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

```bash
ssh agent@agent-lxc                    # via Tailscale (alma) or LAN (jumpy)
tmux new -A -s main                    # attach or create the main session
claude                                 # start Claude Code
```

Inside tmux you can detach with `Ctrl-b d` and reattach with `tmux a` later — work survives SSH disconnection.

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

Recreate: full `terraform apply` + `ansible-playbook` from step 1.

---

## 6. Troubleshooting (top 5)

| Symptom | Diagnosis | Fix |
|---|---|---|
| `terraform apply` hangs at "Still creating" | Token lacks `VM.Audit` etc. — bpg polls 403 | See `homelab/memory/project_proxmox_terraform_token_perms.md`; ensure both user and token have TerraformProv on `/` |
| LXC starts but no IPv4 ("incomplete" in arp from outside) | Missed `static_ip` config or wrong CIDR/gateway | `pct config 210 \| grep net0` on Proxmox; `pct exec 210 -- ip a` |
| Tailscale role: `Permission denied (publickey)` from auth-key task | Auth key revoked / wrong tag / not pre-approved | Mint a new key in admin, update vault, re-run with `--tags tailscale` |
| Ansible: `command not found: claude` for the verify step | `~/.npm-global/bin` not on PATH for the running session | The role sets PATH via `environment:`; if you also touched `.bashrc`, source it or restart shell |
| SSH refuses `agent@agent-lxc` after ssh_hardening | Hardening reloaded sshd but `dev_user_authorized_keys` was empty | Recover via Proxmox console (`pct enter 210`), fix authorized_keys, re-run `--tags base,ssh_hardening` |

### 6.1 If `/dev/net/tun` passthrough fails to apply

If `terraform apply` errors on the `device_passthrough` block (provider schema mismatch on a future bpg version), comment that block out, apply, then manually:

```bash
ssh root@192.168.178.10 'pct set 210 -dev0 /dev/net/tun'
ssh root@192.168.178.10 'pct restart 210'
```

Verify inside the LXC:
```bash
ssh root@192.168.178.10 'pct exec 210 -- ls -l /dev/net/tun'
# expected: crw-rw-rw- 1 nobody nogroup 10, 200 ... /dev/net/tun
```

Open an issue / update the provider once schema-fix lands upstream, then put the block back.

---

## 7. Backups (out of scope here, but…)

This repo does not configure backups. Use Proxmox's `vzdump` against LXC 210 on a schedule. Recommended retention: 7 daily + 4 weekly snapshots to a separate datastore. Configure once in the Proxmox UI under Datacenter → Backup.
