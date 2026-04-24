# Changelog

## 2026-04-23 — Argo Workflows onder GitOps

### Added
- **`kubernetes/infrastructure/argo-workflows/install.yaml`** — gepinde quickstart manifest van Argo Workflows v3.7.3 (upstream release asset) lokaal in repo voor audit-trail
- **`kubernetes/infrastructure/argo-workflows/kustomization.yaml`** — kustomize overlay: namespace `argo` + JSON-patch op `argo-server` Deployment voor `--auth-mode=server` (UI zonder bearer token, conform tutorial stap 2)
- **`apps/infrastructure/argo-workflows.yaml`** — Argo CD Application (sync-wave 5, selfHeal, prune) die bovenstaand kustomize-pad synct

### Why
- Argo Workflows was handmatig via `kubectl apply -f https://.../install.yaml` geïnstalleerd (zie tutorial LFS256) en de `--auth-mode=server` patch was los uitgevoerd. Niet reproduceerbaar, drift-gevoelig.
- Verschuift beheer naar app-of-apps pattern (`apps/root-app.yaml`) — zelfde patroon als cert-manager/argocd.

### Migratie-stappen
1. `ssh jumpy "kubectl delete -f https://github.com/argoproj/argo-workflows/releases/download/v3.7.3/install.yaml -n argo"` — handmatige install opruimen
2. `git add + commit + push` (na confirm)
3. Argo CD root-app pikt `argo-workflows` Application op → kustomize render → deployt opnieuw in namespace `argo`
4. Verifiëren: `kubectl get pods -n argo` → controller + server Running, `argo-server` args bevatten `--auth-mode=server`
5. UI-toegang blijft via `kubectl -n argo port-forward deployment/argo-server 2746:2746` (geen HTTPRoute in deze change — kan later)

## 2026-04-07 — Portainer VM + proxy cleanup + Terraform refactor

### Added
- **Portainer VM** (104, 192.168.178.54) — separate VM for container management UI
  - `docker/portainer/docker-compose.yml` — Portainer CE 2.27.4
  - `ansible/playbooks/deploy-portainer.yml` — deploys Portainer + enables Docker TCP API on tenant/proxy VMs
  - Added to `proxmox-hosts.yml` inventory
- **Terraform `for_each`** — refactored from single VM to map of all VMs (proxy, klant-a/b/c, portainer) with per-VM cores/memory/disk

### Changed
- **Proxy playbook** — added `register` + `--force-recreate` on config change (same pattern as nextcloud playbook)
- **Proxy playbook** — added `owner`/`group` ubuntu + `become: false` for docker commands
- **Static Caddyfile** — synced with Jinja2 template (added React frontend routes + `tls internal`)
- **CLAUDE.md** — added Portainer VM to layout, directory structure, deployment commands, access patterns

### Note
- Portainer VM (104) needs to be provisioned on Proxmox before Ansible deploy
- Terraform provider bug (bpg/proxmox hangs) still applies — may need manual `qm` provisioning
- Docker TCP API (port 2375) on tenant VMs is unencrypted — acceptable on LAN, not for production

## 2026-04-06 — Nextcloud tenant fixes + Ansible improvements

### Fixed
- **PHP memory_limit** raised to 2G on nextcloud + cron containers — openregister/openconnector apps exhaust default 512MB (single 130MB+ allocations)
- **Cron container** now runs as `user: www-data` instead of root — fixes "Console has to be executed with the user that owns config.php" error
- **First run wizard** disabled on klant-a (`occ app:disable firstrunwizard`) — was rendering a frozen modal blocking the entire UI

### Changed
- **Ansible deploy-nextcloud playbook** now registers config file changes and passes `--force-recreate` to `docker compose up` when docker-compose.yml, nginx.conf, or .env have changed

### Verified
- klant-a Nextcloud login + dashboard works after fixes
- Cron jobs executing as www-data (no more ownership errors)

### Known Issues
- openregister `psr/log` version incompatible with PHP in NC 32 (PSR\Log\AbstractLogger declaration error) — upstream app bug
- openconnector SynchronizationService also hits memory limits — 2G should cover it but monitor
- Terraform VM provisioning still broken (bpg/proxmox provider hangs)
- klant-b and klant-c need verification after deploy
- SSH config on jumpy needed `IdentitiesOnly yes` + `IdentityFile` for tenant VM access (too many keys in agent)

## 2026-04-04 — Proxmox VM deployment + Nextcloud tenant stacks

### Added
- **Ubuntu 24.04 cloud template** (VM 9000) on Proxmox laptop node — base image for all future VMs
- **4 VMs** provisioned via `qm` CLI: proxy (.50), klant-a (.51), klant-b (.52), klant-c (.53)
- **Docker Compose stack** for Nextcloud tenants: Nextcloud 32.0.5-fpm + Nginx + MariaDB 11 + Valkey 8
- **Caddy reverse proxy** deployed on VM 100 with `tls internal` (self-signed certs for LAN)
- **Ansible deployment pipeline**: playbooks for nextcloud + proxy, Jinja2 templates for per-tenant .env and Caddyfile, Ansible Vault for secrets
- **Proxmox inventory** (`ansible/inventory/proxmox-hosts.yml`) with 3 tenant VMs + 1 proxy VM
- **Terraform config** (`terraform/nextcloud-vm/`) for Proxmox VM provisioning — bpg/proxmox provider
- **SessionStart hook** for secret hygiene checks (`.gitignore` coverage + tracked secret detection)

### Fixed
- Nginx config: `rewrite ^ /index.php$request_uri` in catch-all location — prevents 403 on Nextcloud app routes like `/apps/dashboard/`
- `.env` removed from git tracking (`git rm --cached`) — was previously committed with secrets
- Snap purged from jumpy VM — freed 6GB, `apt-mark hold snapd` prevents reinstall

### Changed
- `.gitignore` updated with Terraform state files and `.terraform/` directory
- `CLAUDE.md` updated with Proxmox VM deployment pipeline documentation

### Verified
- Nextcloud login works via `https://klant-a.westerweel.work` (Caddy → Nginx → PHP-FPM)
- Ansible deploys to all 3 tenant VMs in parallel
- Cloud-init template cloning works (~4 seconds per VM)

### Known Issues
- Terraform bpg/proxmox v0.99.0 provider hangs during VM creation (config lock timeout) — VMs created manually via `qm` as workaround
- DNS via `/etc/hosts` on alma — no Cloudflare records yet
- Cloudflare API token in git history — should be rotated
- klant-b and klant-c untested (deployed but login not verified)
- Ansible `become: true` + docker socket: need `become: false` for docker commands, ubuntu user must be in docker group

### Next Steps
- Test klant-b and klant-c login
- Install Conduction apps (opencatalogi, openconnector, openregister)
- Deploy React pages on separate VM(s)
- Real DNS via Cloudflare for external access
- Fix Terraform provider or switch to telmate/proxmox
