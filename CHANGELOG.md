# Changelog

## 2026-05-13 — nginx-lab robuustheid: disk-resize + dpkg-recovery

### Fixed
- **`terraform/nginx-lab/main.tf`** — `disk` block toegevoegd. De `disk = 20` in `variables.tf` was decoratief: er stond geen disk-block in `main.tf` zodat de clone gewoon de template-disk (3.5GB) erfde. Apt liep daardoor vol bij Nextcloud + php-extensions. Nu wordt `scsi0` daadwerkelijk gegrowd naar 20GB; cloud-init's growpart breidt partition + ext4 auto uit.
- **`ansible/playbooks/deploy-nginx-lab.yml`** — pre-task `dpkg --configure -a` toegevoegd vóór de apt-update. Herstelt automatisch interrupted package-state (bv. uit een eerdere mislukte run). Idempotent.

### Why
- Eerste end-to-end run viel om op "No space left on device" tijdens apt install op beide VMs; daarna corrupte dpkg state. Beide werden handmatig gefixt (`qm resize`, `dpkg --configure -a`). Met deze fixes overleeft de pipeline een schone `terraform destroy && terraform apply && ansible-playbook` cyclus zonder handmatige interventie.

### Lessons logged uit de eerste run
- `bpg/proxmox` provider's `still creating` hang treedt op als runtime-state niet matcht met de aangevraagde state (`started=false` terwijl cloud-init de VM toch boot). Gefixt door `started=true` (eerdere commit).
- Tijdens een hang worden niet alle initialization-fields (ipconfig0, ciuser, sshkeys) altijd naar Proxmox doorgeduwd. Met `started=true` zou dat probleem zich niet meer voor moeten doen — maar als fallback weet je nu dat `qm set --ipconfig0` / `--sshkeys` + `qm cloudinit update` + reboot de drift handmatig oplost.
- `disk` in een terraform var moet ook in `main.tf` gebruikt worden. Decoratieve vars zijn een fopper.

## 2026-05-13 — Tailscale advertise-routes onder Ansible

### Added
- **`ansible/inventory/hypervisors.yml`** — nieuwe inventory met group `hypervisors`; host `proxmox-laptop` op 192.168.178.10 (root over de homelab-SSH-key). Bedoeld voor hypervisor-niveau config (Tailscale, host-firewall etc.), niet voor tenant-workloads.
- **`ansible/group_vars/hypervisors.yml`** — single source of truth voor `tailscale_advertise_routes`: alle 7 VM-IPs als /32 (50/proxy, 51-53/klant-a-c, 54/portainer, 55-56/nginx-lab-{clean,broken}).
- **`ansible/playbooks/configure-tailscale-routes.yml`** — runt `tailscale set --advertise-routes=...` op alle hypervisors. Print prefs voor- en na, met reminder dat nieuwe routes nog in de Tailscale admin-console goedgekeurd moeten worden.

### Why
- VMs `.55`/`.56` waren niet bereikbaar vanaf alma omdat de Tailscale-subnet-router op Proxmox die /32s niet adverteerde. Manuele `tailscale set` op de Proxmox-host werkt, maar drift sluipt erin zodra je er meerdere VMs bijzet. Single source of truth in group_vars maakt route-uitbreiding 1 regel + 1 playbook-run. `/24` blijft expliciet verboden (kaapt alma's eigen LAN-routing — zie `project_tailscale_subnet_routing`).

### Verify after run
```bash
ssh jumpy
cd ~/homelab/ansible
ansible-playbook -i inventory/hypervisors.yml playbooks/configure-tailscale-routes.yml --check
ansible-playbook -i inventory/hypervisors.yml playbooks/configure-tailscale-routes.yml
# daarna goedkeuren op https://login.tailscale.com/admin/machines
# vervolgens vanaf alma:
ssh ubuntu@192.168.178.55 hostname     # zou moeten antwoorden
```

## 2026-05-13 — nginx-lab: started=true fix

### Fixed
- **`terraform/nginx-lab/main.tf`** — `started = false` → `started = true`. Cloud-init triggert na clone toch een boot; met `started=false` poolt de bpg/proxmox-provider eindeloos op state-drift (de "still creating" hang van ~12 min observed). Met `started=true` matcht terraform-state de runtime-realiteit en finisht apply direct.

## 2026-05-13 — nginx + Nextcloud debug-lab

### Added
- **`terraform/nginx-lab/{main,variables,versions}.tf`** — twee Ubuntu-VMs op Proxmox (`nginx-lab-clean` id=105 op .55, `nginx-lab-broken` id=106 op .56), elk 4GB/2c/20GB, kloon van template 9000, `started=false`.
- **`ansible/inventory/nginx-lab-hosts.yml`** — group `nginx_lab` met beide hosts en per-host `lab_state` (clean | broken).
- **`ansible/playbooks/deploy-nginx-lab.yml`** — var-driven: gemeenschappelijk install-pad (nginx, php8.3-fpm + extensions, mariadb-server, Nextcloud 30.0.4 tarball naar `/var/www/nextcloud`, chown www-data), daarna `when: lab_state == 'broken'`-block dat MariaDB seedt, `occ maintenance:install` draait, gesaboteerde nginx-vhost + PHP memory-override deployt en data-dir permissies omgooit.
- **`ansible/templates/nginx-lab/nginx-broken.conf.j2`** — realistische Nextcloud-vhost met 2 ingebouwde bugs: `fastcgi_pass` naar php8.1-socket (terwijl 8.3 draait) en `client_max_body_size 1M`.
- **`~/Homelab/learning/nginx-debug-lab.md`** — lab-doc met provisioning-commands, debug-traject zonder spoilers, en tools-cheatsheet.

### Why
- Mark loopt tegen kennis-gaten in nginx + Nextcloud bare-metal aan. Container-stack verbergt te veel. Doel: één VM van scratch zelf configureren, één gesaboteerde VM debuggen — diversiteit van symptomen (nginx ↔ PHP-bridge, request-handling, PHP-runtime, NC-applaag, filesystem-permissies) traint vinden-via-symptoom in plaats van fix-via-recept.

### Verify after apply
```bash
cd ~/Homelab/homelab/terraform/nginx-lab && terraform plan       # expect 2 VMs to add
cd ~/Homelab/homelab/ansible
ansible-playbook -i inventory/nginx-lab-hosts.yml playbooks/deploy-nginx-lab.yml --check
```
Daarna http://192.168.178.55 (clean: nginx default page of 502) versus http://192.168.178.56 (broken: 502 Bad Gateway als eerste symptoom).

## 2026-04-26 — Argo Events onder GitOps

### Added
- **`kubernetes/infrastructure/argo-events/install.yaml`** — gepinde v1.9.10 upstream manifest (CRDs `EventBus`/`EventSource`/`Sensor` + 4 controllers).
- **`kubernetes/infrastructure/argo-events/eventbus-default.yaml`** — `EventBus default` met JetStream (1 replica voor homelab; productie wil 3 voor raft quorum). Sensors zonder expliciete `eventBusName` defaulten hierop.
- **`kubernetes/infrastructure/argo-events/kustomization.yaml`** — overlay namespace `argo-events`.
- **`apps/infrastructure/argo-events.yaml`** — Argo CD Application (sync-wave 5).

### Why
- Vervolgstap na Workflows + Rollouts in de Argo-suite. Doel: event-driven triggers (Slack, GitHub, webhook) richting Argo Workflows of andere K8s-resources. Niet productief gebruik nu — leeromgeving voor Hydra-achtige patterns later (zie `~/Homelab/learning/argo-events-slack-hydra.md`).

### Verify after sync
```
ssh jumpy 'kubectl get pods -n argo-events; kubectl get crd | grep -E "(eventsources|sensors|eventbus)\.argoproj"; kubectl get eventbus -n argo-events'
```
Verwacht: 4 controller-pods Running, 3 CRDs aanwezig, `eventbus default` Active met 1 NATS-pod.

## 2026-04-24 — Argo Rollouts onder GitOps

### Added
- **`kubernetes/infrastructure/argo-rollouts/install.yaml`** — gepinde v1.8.3 upstream manifest (CRDs + controller + RBAC).
- **`kubernetes/infrastructure/argo-rollouts/kustomization.yaml`** — kustomize overlay: namespace `argo-rollouts`.
- **`apps/infrastructure/argo-rollouts.yaml`** — Argo CD Application (sync-wave 5, selfHeal, prune).

### Why
- LFS256 Lab 5.1 vraagt om een handmatige `kubectl apply` van de install.yaml. Zelfde patroon als argo-workflows vermijden we — niet reproduceerbaar, drift-gevoelig. Via app-of-apps pattern blijft de state declaratief.

### Verify after sync
```
ssh jumpy 'kubectl get pods -n argo-rollouts; kubectl get crd | grep argoproj.io'
```
Verwacht: argo-rollouts controller pod Running, CRDs `rollouts.argoproj.io` + 4 andere.

## 2026-04-24 — Argo Workflows executor RBAC

### Added
- **`kubernetes/infrastructure/argo-workflows/executor-rbac.yaml`** — `Role workflow-executor` + `RoleBinding workflow-executor-default` die `create`/`patch` rechten geven op `workflowtaskresults` en `list`/`watch`/`patch` op `workflowartifactgctasks` voor ServiceAccounts `default` en `argo` in namespace `argo`.

### Changed
- **`kubernetes/infrastructure/argo-workflows/kustomization.yaml`** — neemt nu ook `executor-rbac.yaml` als resource mee.

### Why
- Eerste hello-world submit (`argo submit ... examples/hello-world.yaml`) liep door de main-container heen (`hello world` in logs) maar faalde in de wait-sidecar met `workflowtaskresults.argoproj.io is forbidden`. Upstream `install.yaml` bevat bewust geen executor-RBAC — bedoeld als operator-verantwoordelijkheid per namespace. Zonder deze binding kan geen enkele workflow terugrapporteren aan de controller.

### Verify after sync
```
ssh jumpy 'argo submit -n argo --watch https://raw.githubusercontent.com/argoproj/argo-workflows/main/examples/hello-world.yaml'
```
Verwacht: `Status: Succeeded` (zonder `--serviceaccount`-flag).

## 2026-04-24 — jumpy-maintenance Ansible role

### Added
- **`ansible/roles/jumpy-maintenance/`** — eerste Ansible role in de repo. Installeert op jumpy:
  - `/etc/systemd/journald.conf.d/50-jumpy-size.conf` — journald cap op 200M, houdt 500M vrij
  - `/usr/local/sbin/jumpy-maintenance.sh` — idempotent script: apt autoremove/clean, journal vacuum, prune rotated `*.gz` ouder dan 30d, `go clean -cache` voor user `jump`
  - `jumpy-maintenance.service` + `.timer` — weekly run (Sun 04:00, Persistent=true, RandomizedDelaySec=15min)
  - `/etc/profile.d/jumpy-disk.sh` — toont disk-usage bij interactive login; geel bij ≥70%, rood bij ≥85%
- **`ansible/playbooks/jumpy-maintenance.yml`** — deploy-playbook voor de role
- **`ansible/inventory/management-hosts.yml`** — nieuwe inventory voor utility/bastion VMs, begint met `jumpy` (group `management`). Los van `proxmox-hosts.yml` omdat jumpy op VMware draait, niet Proxmox.

### Why
- Op 2026-04-24 liep jumpy disk 100% vol: een GDM/X.Org retry-loop (kernel 6.17 upgrade) produceerde in 7 dagen 2.7 GB syslog + 90 MB wtmp + 83 MB auth.log. Root-cause (GNOME) is opgeruimd (19 GB → 9.9 GB), maar er was geen preventie: geen journald size-cap, geen periodieke apt autoremove, geen disk-signaal bij login. Deze role legt dat vast.

### Deploy
```
cd ansible
ansible-playbook -i inventory/management-hosts.yml playbooks/jumpy-maintenance.yml --ask-become-pass
```
(`--ask-become-pass` nodig omdat user `jump` nog geen passwordless sudo heeft)

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
