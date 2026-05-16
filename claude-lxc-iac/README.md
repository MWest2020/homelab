# claude-lxc-iac

Isolated development LXC on Proxmox for running Claude Code remotely, accessed via SSH over Tailscale. Reproducible (Terraform + Ansible), single-purpose, audit-friendly.

This is a subfolder of the `homelab/` repo (see ADR-012 in `docs/decisions.md`). All commands assume you're inside `~/homelab/claude-lxc-iac/` on jumpy.

Aimed at the operator's personal MWest2020 GitHub work. Work-account / client repos belong on `alma`, not here.

## What's in the box

After two boring commands you get:
- Proxmox LXC `agent-lxc` (id 210, Ubuntu 24.04 LTS, 2c/4G/50G, unprivileged)
- Static IP on the homelab LAN, Tailscale-reachable as `agent-lxc` with tag `tag:homelab-router`
- A non-root user `agent` with SSH-key-only login, OpenSSH hardened (`PermitRootLogin no`, `PasswordAuthentication no`)
- Node.js 20 from NodeSource, Claude Code installed via `npm`
- A sanitised copy of the operator's `~/.claude/settings.json` and `~/.claude/CLAUDE.md` (no credentials, no machine-specific hooks)
- A dedicated GitHub SSH key (`id_ed25519_github`) and git identity for `mwest2020 / mwesterweel@hotmail.com` — public key printed at the end of the run, you add it to GitHub manually

## Prerequisites

Done **before** you run `terraform apply`:

1. **Proxmox API token** — create `terraform@pve!automation-lxc` in the Proxmox UI. Required permissions:
   ```
   Datastore.AllocateSpace, Datastore.Audit,
   VM.Allocate, VM.Audit, VM.Clone,
   VM.Config.CDROM, VM.Config.Cloudinit, VM.Config.CPU,
   VM.Config.Disk, VM.Config.HWType, VM.Config.Memory,
   VM.Config.Network, VM.Config.Options,
   VM.Migrate, VM.Monitor, VM.PowerMgmt,
   Sys.Audit, Sys.Console, Sys.Modify,
   Pool.Allocate, SDN.Use
   ```
   Apply role on `/` (or scope tighter if you prefer); also assign the same role to the parent user `terraform@pve` so token-privsep doesn't strip permissions away.
2. **Ubuntu 24.04 LXC template** downloaded on Proxmox:
   ```bash
   ssh root@192.168.178.10 'pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst'
   ```
3. **Tailscale auth key** — admin console → Settings → Keys → Generate auth key. Settings:
   - Reusable: **off**
   - Ephemeral: **off**
   - Pre-approved: **on**
   - Tags: `tag:homelab-router`
   - Valid for one day (it gets used once during Ansible run)
4. **SSH public key** for login as the `agent` user — by default `~/.ssh/id_ed25519_homelab.pub` on jumpy.
5. **Operator's `~/.claude/settings.json` and CLAUDE.md** present on the Ansible controller (alma or jumpy with operator's home dir). The role reads them at deploy-time, sanitises, and copies a subset to the LXC.

## Quick start

Two commands. The pre-flight prep above is the actual work; these two just run the resulting machinery.

```bash
# Step 1 — provision the LXC (from jumpy)
cd terraform
export PROXMOX_VE_API_TOKEN_LXC='terraform@pve!automation-lxc=<secret>'
terraform init
terraform apply
# note the IP from terraform output

# Step 2 — configure the LXC (from jumpy, vault password in ~/.vault_pass)
cd ../ansible
export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass
# update inventory.yml to point ansible_host to the IP from step 1
ansible-playbook -i inventory.yml playbook.yml -vv | tee /tmp/agent-lxc-ansible.log
```

After step 2 succeeds, SSH in to finish two interactive one-offs:
```bash
ssh agent@agent-lxc
claude   # logs in interactively to your Anthropic account
cat ~/.ssh/id_ed25519_github.pub   # paste into https://github.com/settings/keys
```

## Where to find what

- `docs/plan.md` — design plan with sanitisation analysis (read this first if you're reviewing)
- `docs/runbook.md` — every operational step (provision, re-run, troubleshoot, destroy)
- `docs/decisions.md` — ADR-style entries for the non-trivial calls
- `terraform/terraform.tfvars.example` — variable shape (copy to `terraform.tfvars`, fill in)
- `ansible/inventory.yml.example` — inventory shape
- `ansible/vault/secrets.yml.example` — vault shape
- `ansible/roles/*/` — one role per concern, runnable independently with `--tags`

## Scope of this repo

In: the single Claude Code dev LXC and what it needs to run.
Out: Tailscale ACL policy changes (separate concern), backups (configure Proxmox `vzdump` separately), monitoring, CI/CD for this repo, MCP server configuration, Docker / Podman / k8s tooling.
