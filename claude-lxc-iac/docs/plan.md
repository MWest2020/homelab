# Plan v2 — Claude Code dev LXC on Proxmox

**Status**: draft, awaiting operator review. **Geen Terraform of Ansible code voor akkoord.** Vorige plan-v1 (AlmaLinux) is overruled door de v2-spec; deze plan vervangt 'm volledig.

Locatie: `~/homelab/claude-lxc-iac/` (subdir van de homelab-repo — niet meer een aparte repo zoals oorspronkelijk gepland; zie ADR-012).

## 1. Vaste parameters (operator-decided, geen onderhandeling)

| Item | Waarde |
|---|---|
| OS | Ubuntu 24.04 LTS — `local:vztmpl/ubuntu-24.04-standard_*.tar.zst` |
| `vm_id` | `210` |
| `hostname` (LXC + tailscale) | `claude-lxc` |
| `dev_user` | `gongoeloe` |
| Resources | 2 cores, 4096MB RAM, 1024MB swap, 50GB rootfs op `local-lvm` |
| Network | **Static IP** — operator vult `static_ip` / `gateway` / `cidr` in tfvars; fail loudly bij missing |
| Unprivileged | `true` |
| Features | `nesting=1` (voor Tailscale tun-passthrough) |
| `onboot` | `true` |
| Tailscale-tag | `tag:homelab-router` (hergebruikt, geen ACL-werk) |
| Tailscale auth | via Ansible vault var `tailscale_authkey` |
| API-token | `terraform@pve!automation-lxc`, secret via env `PROXMOX_VE_API_TOKEN_LXC` |
| GitHub-identiteit | nieuwe ed25519-key op LXC, `mwest2020 / mwesterweel@hotmail.com` |

## 2. Sanitiserings-analyse van alma's `~/.claude/`

Wat ik op alma vond en wat de plan is voor de LXC.

### `~/.claude/settings.json` — 90 regels gelezen

**Inhoud (sectie voor sectie):**

| Section | Inhoud (samengevat) | Plan voor LXC |
|---|---|---|
| `permissions.deny` | 36 regels — bash/write deny-patterns (git force-push, kubectl delete, rm -rf, secret-files etc.) | **KEEP**. Universele safety, evenzo waardevol op LXC. |
| `hooks.SessionStart/PreToolUse/PostToolUse` | Verwijst naar `/home/gongoeloe/.claude/hooks/*.sh` (alma-specifieke scripts) | **STRIP**. Paths bestaan niet op LXC. Operator kan eigen hooks later toevoegen. |
| `enabledPlugins` | `gopls-lsp@claude-plugins-official`, `claude-hud@claude-hud` | **STRIP**. Plugins worden lokaal beheerd via marketplace; LXC start vanaf nul. |
| `extraKnownMarketplaces` | Verwijst naar `github:jarrodwatts/claude-hud` | **STRIP**. Geen MCP per spec, en marketplace-state is environment-specifiek. |
| `theme` | `"auto"` | **KEEP**. Harmless preference. |
| `skipAutoPermissionPrompt` | `true` | **KEEP**. Operator-preference, geldt overal. |

**Niet aanwezig in settings.json** (goed nieuws — niets te lekken):
- Geen `oauth*` / `credentials*` / `api_key*` keys — die zitten in `.credentials.json` (mode 0600), die we NIET lezen of synchroniseren
- Geen `projects` history blob
- Geen MCP server config (zit elders, out-of-scope per spec)

### Resulterende `settings.json` voor LXC

```json
{
  "permissions": {
    "deny": [/* alle 36 patterns 1:1 overgenomen */]
  },
  "theme": "auto",
  "skipAutoPermissionPrompt": true
}
```

Mode `0600`, owner `gongoeloe:gongoeloe`. Gedrop't naar `/home/gongoeloe/.claude/settings.json`.

### `~/.claude/CLAUDE.md` — 166 regels gelezen

**Inhoud (per sectie):**

| Sectie | Verbatim/sanitised? |
|---|---|
| Solution Philosophy | **Verbatim** |
| Git Operations (non-negotiable) | **Verbatim** |
| Destructive Operations | **Verbatim** |
| Infrastructure Changes | **Verbatim** |
| Secrets and Credentials | **Verbatim** |
| Node / NPM Supply Chain | **Verbatim**, met één issue: regel ~93 verwijst naar `bash ~/projects/workstation-security/common/install-pm-cooldown.sh`. Dat pad bestaat niet op LXC. Twee opties: |
| ↳ Optie A | Verbatim laten, accept dat het commando faalt als operator 't ooit uitvoert op LXC |
| ↳ Optie B | Vervangen door comment: `# Pad geldt alleen op alma — repliceer of skip op andere hosts` |
| Shell Scripts (Google style) | **Verbatim** |
| Post-Action Verification | **Verbatim** |
| Changelog en Documentation | **Verbatim** |
| General Conduct | **Verbatim** |

Plus append van de SCOPE-sectie uit de spec (MWest2020-only).

### Andere `~/.claude/` items — NIET syncen

| Item | Waarom niet |
|---|---|
| `backups/`, `cache/`, `channels/`, `file-history/`, `ide/`, `image-cache/`, `paste-cache/`, `plans/`, `policy-limits.json`, `projects/`, `scripts/`, `session-env/`, `sessions/`, `shell-snapshots/`, `tasks/`, `telemetry/` | Runtime-state per machine; geen waarde op verse LXC |
| `commands/`, `hooks/`, `memory/`, `plugins/`, `skills/` | Alma-specifiek; operator kan handmatig opbouwen op LXC indien gewenst |
| `.credentials.json` | **NOOIT lezen** — bevat OAuth-state. Operator logt op LXC opnieuw in via `claude` interactive |
| `history.jsonl`, `mcp-needs-auth-cache.json`, `.last-cleanup` | Cache-state |
| `*.bak` files | Backups van settings.json en CLAUDE.md, irrelevant |

**Beslispunt voor jou**: Optie A of B voor de `~/projects/workstation-security/...` regel in CLAUDE.md?

## 3. Variabele surface (Terraform)

`*.tfvars` gitignored; `terraform.tfvars.example` levert vorm-only.

| Variabele | Type | Default | Doel |
|---|---|---|---|
| `proxmox_api_url` | string | `https://192.168.178.10:8006` | API endpoint |
| `proxmox_api_token` | string (sensitive) | — | Env: `PROXMOX_VE_API_TOKEN_LXC`. Format: `terraform@pve!automation-lxc=<uuid>` |
| `proxmox_insecure` | bool | `true` | Selfsigned cert in homelab |
| `node_name` | string | `proxmox` | Proxmox-node-naam |
| `vm_id` | number | `210` | Vast per spec |
| `hostname` | string | `claude-lxc` | Vast per spec |
| `template_file_id` | string | `local:vztmpl/ubuntu-24.04-standard_<INVULLEN>_amd64.tar.zst` | Operator vult exacte filename in na `pveam download` |
| `bridge` | string | `vmbr0` | LAN bridge |
| `cores` | number | `2` | Vast per spec |
| `memory_mb` | number | `4096` | Vast per spec |
| `swap_mb` | number | `1024` | Vast per spec |
| `rootfs_storage` | string | `local-lvm` | Vast per spec |
| `rootfs_size_gb` | number | `50` | Vast per spec |
| `static_ip` | string | — (REQUIRED, no default) | `192.168.178.x` (operator vult in) |
| `gateway` | string | `192.168.178.1` | Standaard homelab-gateway |
| `cidr` | number | `24` | `/24` LAN |
| `ssh_public_key_path` | string | `~/.ssh/id_ed25519_homelab.pub` | Pad op operator-workstation |

### Random root password
- `random_password` resource (length=32, special=true)
- Injected via `initialization.user_account.password`
- Output `root_initial_password`, `sensitive = true`
- Runbook: `terraform output -raw root_initial_password` → eenmalig kopiëren, daarna SSH-key

### Outputs
- `container_id` (= vm_id)
- `assigned_ip` (= static_ip, voor verbeterde DX)
- `next_steps` (= multi-line: "Run `ansible-playbook ...`")
- `root_initial_password` (sensitive)

## 4. Variabele surface (Ansible)

`ansible/group_vars/claude_dev.yml` (committed, niet-secret) + `ansible/vault/secrets.yml` (encrypted, gitignored).

| Variabele | Type | Default | Bron |
|---|---|---|---|
| `dev_user` | string | `gongoeloe` | group_vars |
| `dev_user_authorized_keys` | list[string] | `[]` (operator vult in) | group_vars — pubkeys voor SSH-login als dev_user |
| `dev_user_nopasswd_sudo` | bool | `false` | group_vars — operator kan op `true` zetten, default off |
| `locale` | string | `en_US.UTF-8` | group_vars |
| `timezone` | string | `Europe/Amsterdam` | group_vars |
| `tailscale_hostname` | string | `claude-lxc` | group_vars |
| `tailscale_tags` | list[string] | `["tag:homelab-router"]` | group_vars |
| `tailscale_authkey` | string (vault) | — | `ansible/vault/secrets.yml`, encrypted |
| `node_major_version` | number | `20` | group_vars |
| `git_user_name` | string | `mwest2020` | group_vars |
| `git_user_email` | string | `mwesterweel@hotmail.com` | group_vars |
| `claude_md_pm_cooldown_strategy` | string (`keep`/`strip`) | (uit open-vraag #1 hieronder) | group_vars |

## 5. Rol-by-rol outline (geen code geschreven)

### `roles/base/`
- `apt update` + `apt dist-upgrade -y` (security-updates inbegrepen)
- Install: `sudo`, `tmux`, `git`, `curl`, `ca-certificates`, `gnupg`, `htop`, `vim`, `unzip`, `jq`, `build-essential`
- `user` module: `gongoeloe`, group `sudo`, shell `/bin/bash`, home `/home/gongoeloe`
- `authorized_key` module: alle pubkeys uit `dev_user_authorized_keys`
- Conditioneel: NOPASSWD-sudo-drop-in als `dev_user_nopasswd_sudo = true`
- `locale_gen` voor en_US.UTF-8; `timedatectl set-timezone Europe/Amsterdam` met `changed_when`-guard
- Niet in deze rol: SSH-hardening, tailscale (eigen rollen)

### `roles/ssh_hardening/`
- Template `/etc/ssh/sshd_config.d/10-hardening.conf`:
  - `PasswordAuthentication no`
  - `PermitRootLogin no`
  - `PubkeyAuthentication yes`
  - `AllowUsers {{ dev_user }}`
- Handler: `systemctl reload ssh` (Ubuntu service heet `ssh`, niet `sshd`)
- Post-handler `wait_for` op port 22 + try-ssh als `dev_user` met `delegate_to: localhost`, `ansible_connection: ssh`. Lockout-prevention.

### `roles/tailscale/`
- Add `signed-by` apt repo: GPG-key naar `/usr/share/keyrings/tailscale-archive-keyring.gpg`, `/etc/apt/sources.list.d/tailscale.list`
- `apt install -y tailscale`
- `systemctl enable --now tailscaled`
- `tailscale up --hostname={{ tailscale_hostname }} --advertise-tags={{ tailscale_tags | join(',') }} --ssh=false --auth-key={{ tailscale_authkey }}` met `creates: /var/lib/tailscale/tailscaled.state` als idempotency-guard
- `--ssh=false` expliciet — vanille OpenSSH blijft auth-path

### `roles/nodejs/`
- Add NodeSource signed-by apt repo (`https://deb.nodesource.com/node_20.x noble main`), GPG verify
- `apt install -y nodejs`
- Als `dev_user`: `npm config set prefix ~/.npm-global`
- Drop `~/.bashrc` `export PATH="$HOME/.npm-global/bin:$PATH"` regel via `blockinfile` met begin/end-marker (idempotent)

### `roles/claude_code/`
- `npm install -g @anthropic-ai/claude-code` als `dev_user`
- Verify: `claude --version` → `register: claude_version`, `failed_when: claude_version.rc != 0`
- Template `~/.tmux.conf`:
  ```
  set -g mouse on
  set -g history-limit 50000
  set -g default-terminal "screen-256color"
  ```
- **Settings sync** (per sanitisering-analyse hierboven):
  - Lokaal op de Ansible-controller (alma): lees `~/.claude/settings.json`, parse JSON, strip `hooks` + `enabledPlugins` + `extraKnownMarketplaces` velden via `set_fact` + `from_json`/`to_json`
  - Drop het ge-sanitiseerde resultaat naar `/home/gongoeloe/.claude/settings.json` op de LXC, mode `0600`, owner `gongoeloe:gongoeloe`
- **CLAUDE.md sync**:
  - Lees alma's `~/.claude/CLAUDE.md`
  - Pas één van de twee strategieën toe op de pm-cooldown-script-regel (per open-vraag #1)
  - Append SCOPE-sectie (verbatim uit spec)
  - Drop naar `/home/gongoeloe/.claude/CLAUDE.md`, mode `0644`, owner `gongoeloe:gongoeloe`
- Print: `Claude Code is installed. Run claude interactively to complete account login. Browser flow falls back to copy-paste URL on headless systems.`

### `roles/github_identity/`
- `community.crypto.openssh_keypair`: `~/.ssh/id_ed25519_github`, type `ed25519`, comment `claude-lxc-github`, owner `gongoeloe`, mode `0600`/`0644`
- `~/.ssh/config`: blockinfile met de github-host-block
- `~/.gitconfig`: template met `[user] name/email`, `[init] defaultBranch=main`, `[pull] rebase=false`
- Read pubkey terug, print met banner: `Add this key to GitHub at https://github.com/settings/keys with title 'claude-lxc' and Authentication+Signing scope. Do NOT enable for SSO of organisations other than personal repos.`
- **Niet** automatisch uploaden naar GitHub (out of scope per spec)

## 6. `/dev/net/tun` voor unprivileged LXC

Tailscale heeft een tun-device nodig. Plan: provider-native via `bpg/proxmox` (zie `proxmox_virtual_environment_container.device_passthrough` block in 0.106-docs). Tijdens implementatie verifiëren of dat schema werkt voor unprivileged LXC. Zo niet:
- Documenteer in `runbook.md` de exacte `pct set 210 -dev0 /dev/net/tun` / config-file edit
- Verifieer dat dat werkt vóór "done" claimen
- ADR-entry in `decisions.md` met de keuze

## 7. `.gitignore` plan

```
# Terraform
.terraform/
.terraform.lock.hcl
*.tfstate
*.tfstate.*
*.tfvars
!*.tfvars.example
crash.log
crash.*.log

# Ansible
ansible/inventory.yml
!ansible/inventory.yml.example
*.retry
ansible/vault/secrets.yml
!ansible/vault/secrets.yml.example
.vault_pass

# Generated SSH keys (mochten ze ooit lokaal landen)
id_ed25519_*
!id_ed25519_*.pub
*.pem
*.key

# Editor / OS
.vscode/
.idea/
*.swp
*~
.DS_Store
```

## 8. Open vragen voor operator

1. **CLAUDE.md cooldown-script regel** — Optie A (verbatim laten staan, faalt als ooit uitgevoerd) of Optie B (vervangen door `# Pad geldt alleen op alma`)? Mijn voorkeur: **B**, want anders is het een latent-fout commando in je global rules.

2. **`static_ip` waarde** — welke IP wil je geven? `192.168.178.58` zou logisch zijn (na `.55`/`.56`/`.57` van de nginx-labs en future-proof voor andere LXCs in `.58–.69` range). Of een ander vrij IP?

3. **`dev_user_authorized_keys` lijst** — alleen je homelab-key (`id_ed25519_homelab.pub`), of meerdere (bv. ook een laptop-key)?

4. **`dev_user_nopasswd_sudo`** — default `false` (operator voert wachtwoord in voor sudo). Wil je 'm op `true`? Trade-off: convenience vs. defense-in-depth.

5. **Ubuntu template exact filename** — heb je 'm al gedownload op proxmox? Exacte naam (bv. `ubuntu-24.04-standard_24.04-1_amd64.tar.zst`) zodat ik die als default in `terraform.tfvars.example` kan zetten?

6. **CLAUDE.md SCOPE-sectie hostname** — spec zegt verbatim `claude-lxc`. Match je hostname. Eens dat we 't 1:1 overnemen?

7. **Vault password** — hoe wil je de Ansible vault unlocken? Opties:
   - **Env-var** `ANSIBLE_VAULT_PASSWORD_FILE` wijst naar een file op je workstation (boring, auditeerbaar)
   - **Prompt** elke run (`--ask-vault-pass`)
   - **External secret manager** (overkill voor één key)
   Mijn voorkeur: optie 1 met een file in je homelab-wide `~/.vault_pass` (al gitignored).

## 9. STOP

Geen code geschreven. Wachten op antwoorden op de 7 open vragen + akkoord op de sanitiserings-aanpak. Implementatie-volgorde na akkoord:

1. `git init` + `.gitignore` + `README.md` skeleton + `terraform.tfvars.example` + `vault/secrets.yml.example`
2. `terraform/` (one shot, klein) → `terraform plan` check
3. `ansible/roles/base/` → tagged playbook-run
4. `ansible/roles/ssh_hardening/`
5. `ansible/roles/tailscale/`
6. `ansible/roles/nodejs/`
7. `ansible/roles/claude_code/` (incl. settings + CLAUDE.md sync)
8. `ansible/roles/github_identity/`
9. `docs/runbook.md` + `docs/decisions.md`
10. End-to-end test: destroy → terraform apply → ansible-playbook → SSH + claude --version

Elk van die stappen één-voor-één, niet allemaal tegelijk.
