# Changelog

## 2026-06-11 — Fix: hubble-relay i/o timeout (UFW dropte pod→host:4244)

### Fixed
- **`ansible/playbooks/prepare-nodes.yml`** — UFW liet alleen `192.168.178.0/24` toe. De
  `hubble-peer`-service heeft **host-network** backends (cilium-agents op `:4244`); een pod
  (hubble-relay, `10.200.x`) die via de ClusterIP daarheen ging arriveerde met pod-IP op de
  host-INPUT-chain → UFW dropte 'm → `dial tcp 10.32.0.250:443: i/o timeout`, relay in CrashLoop.
  Regel toegevoegd: `ufw allow from 10.200.0.0/16` (pod-CIDR → host). Live toegepast op alle
  6 nodes (.202-.207) én in de playbook gezet. Relay daarna `1/1 Ready` binnen ~20s.

## 2026-06-07 — proxmox-migration Fase 1+2: 3-node Proxmox-cluster + HA-K8s-bootstrap

### Context
- Fase 1 (USB): 3 baremetal nodes gewipet → **Proxmox VE 8.4**, hostnames px-01/02/03 (.11/.12/.13), `pvecm` → **3-node cluster (quorate, geen QDevice)**. Tailscale per host. Per-host template-reeksen (VMID's zijn cluster-breed uniek): px-01 9000/01/02, px-02 9010/11/12, px-03 9020/21/22.
- Fase 2: terraform rolt **6 VM's** uit (3 CP .202-.204 + 3 worker .205-.207), daarna HA-bootstrap.

### Added
- **`scripts/bootstrap-proxmox-token.sh`** — terraform API-token + rol `TerraformProv` op een cluster (idempotent, secret 1x geprint).
- **`ansible/playbooks/build-k8s-templates.yml`** — bouwt 9000/CP/worker-templates per host (`tmpl_base` host-var; VMID's cluster-breed uniek + local-lvm kan niet cross-node clonen).
- **`ansible/playbooks/bootstrap-ssh-key.yml`** — jumpy-key uitrollen via `--ask-pass` (kip-ei), daarna key-based.
- **`ansible/inventory/group_vars/proxmox_cluster.yml`** + route-advertising voor .201-.207 (kube-vip VIP + VM's) incl. IP-forwarding.
- **kube-vip HA-bootstrap** in `kubeadm-bootstrap.yml`: kube-vip v1.2.0 static pod (VIP .201, ARP, leaderElection) + `kubeadm init --upload-certs` op de eerste CP + control-plane-joins + worker-joins.

### Changed
- **`ansible/files/kubeadm-config.yaml`** → **v1beta4** (K8s 1.36), controlPlaneEndpoint .201, cgroupDriver systemd via KubeletConfiguration.
- **`ansible/inventory/hosts.yml.example`** → 6-VM HA-layout (control_plane 3 + workers 3, user ubuntu).
- **`ansible/inventory/hypervisors.yml`** → `proxmox_cluster`-groep (Tailscale-IP's, `tmpl_base`, IdentitiesOnly=yes).
- **`terraform/k8s-cluster/`** → endpoint px-01, 6 VM's met per-node `template_vm_id`; tfvars.example zonder comment-toggle.

### Why / supply chain
- kube-vip **v1.2.0** (2026-05-28) upstream-geverifieerd, buiten 7-daagse cooldown. bpg blijft `~> 0.106.0`.
- Per-host template-reeksen: VMID's zijn cluster-breed uniek (`reference_proxmox_cluster_vmid`).

### Verify (vanaf jumpy)
```bash
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/prepare-nodes.yml
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-install-packages.yml
ansible-playbook -i inventory/hosts.yml playbooks/kubeadm-bootstrap.yml
ssh ubuntu@192.168.178.202 'kubectl get nodes'   # 6 nodes, 3 control-plane
```

## 2026-06-05 — proxmox-migration Fase 0: K8s-pin → 1.36.1 + Terraform `k8s-cluster`-module

### Context
- Greenfield-rebuild van het baremetal K8s-cluster (1.29) naar **VM's op een 3-node Proxmox-cluster** (Optie A: de 3 baremetal nodes vormen het cluster, laptop blijft standalone; oneven quorum, geen QDevice). Doel-topologie: **3 control-plane (HA) + 3 workers** op K8s **1.36.1**, control-plane-endpoint als **VIP .201 (kube-vip)** zodat jumpy's kubeconfig ongewijzigd blijft. Volledig plan: `openspec/changes/proxmox-migration/`.
- Deze entry = **Fase 0** (geen risico): versie-bump + Terraform-module scaffolden, te valideren op de standalone laptop vóór er baremetal wordt gewipet.

### Changed
- **`ansible/group_vars/k8s_cluster.yml`** — `k8s_version` 1.29 → **1.36**. `k8s_apt_repo`/`k8s_apt_repo_key_url` nu **afgeleid van `k8s_version`** (`v{{ k8s_version }}`) → één plek om te bumpen. De v1.36-repo serveert momenteel patch 1.36.1 (latest, 2026-05-12).
- **`ansible/playbooks/kubeadm-install-packages.yml`** — de play-level override-vars (`v1.31`-key + `v1.29`-repo) verwijderd; het playbook erft nu de repo/key uit group_vars. Dit was de bron van de versie-drift (key v1.31 vs repo v1.29).

### Added
- **`terraform/k8s-cluster/`** — nieuwe module (`bpg/proxmox ~> 0.106`), data-driven via `var.vms` (per VM `vm_id`/`node_name`/`ip`/`template_vm_id`/`role`). **Template-per-shape, géén post-clone hardware-overrides** (conform `feedback_template_per_size`: bpg hangt op cpu/memory/disk-overrides na clone — bevestigd op 0.69 én 0.106). Hardware komt uit templates 9001 (CP 4c/8GB/50GB) + 9002 (worker 4c/16GB/50GB), te bouwen met qm. Module = clone + network + cloud-init + agent, anti-affinity via `node_name`. **Veilige lege default** (`vms = {}` → apply doet niets tot opt-in via tfvars). `terraform.tfvars.example`: qm-template-recept + Fase-0 wegwerp-test-VM op de laptop + (commented) Fase-2 6-VM-layout (VMID 110–115, IP .202–.207).

### Why / supply chain
- Versies upstream-geverifieerd: K8s **1.36.1** is de laatste 1.36-patch. bpg/proxmox **0.108.0** (2026-06-01) is **bewust gemeden** — binnen de 7-daagse cooldown; module pint `~> 0.106` (uniform met bestaande modules, buiten cooldown).
- Geen live cluster geraakt: dit zijn alleen IaC-bestanden. Data op de oude baremetal nodes (canary-Nextcloud + minio) is bewust wegwerpbaar (config zit in git/Argo CD).

### Verify (vanaf jumpy, na push + `git pull`)
```bash
cd ansible && ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/kubeadm-install-packages.yml
cd ../terraform/k8s-cluster && terraform fmt -check && terraform init && terraform validate
```

## 2026-06-02 — node-onderhoud: generieke maintenance-role + drain-aware update-playbook

### Context
- `node-02` (.203) MOTD toonde 80 pending updates + *restart required*. Inventarisatie: alleen **jumpy** had onderhoud (`jumpy-maintenance` role: journald-cap + wekelijkse cleanup-timer). De K8s-nodes (cp-01/.201, node-01/.202, node-02/.203) en de Proxmox-VM-fleet (proxy/.50, nextcloud-tenants/.51-.53, portainer/.54) hadden géén journald-cap en géén onderhouds-loop. Package-updates op de nodes liepen alleen via de zware `prepare-nodes.yml` (bootstrap).

### Added
- **`ansible/roles/node-maintenance/`** — generieke, geparametriseerde variant van `jumpy-maintenance` (zónder de jumpy-specifieke go-cache-clean). Capt journald (`50-node-size.conf`, default 200M/500M-keep-free), installeert `node-maintenance.sh` + systemd-service + -timer (default `Sun 04:00`, weekly) die `apt autoremove --purge` + `apt clean` + `journalctl --vacuum-size` + prune van `*.gz`-logs >30d doet, en een login-disk-MOTD (`/etc/profile.d/node-disk.sh`, >70% geel / >85% rood). Tunables in `defaults/main.yml` (`nm_*`).
  - **Security-updates: unattended-upgrades** (industrie-standaard). Installeert `unattended-upgrades`, enables de periodieke timer (`20auto-upgrades`) en pint gedrag (`52node-unattended.conf`): **alleen de `-security`-pocket** (Ubuntu-default origins ongewijzigd, bewust níét verbreed) en **`Automatic-Reboot "false"`**. `apt-mark hold` op kubelet/kubeadm/kubectl wordt gerespecteerd → clusterversie nooit geraakt. Volledige dist-upgrades + reboots blijven `node-update.yml`.
- **`ansible/playbooks/node-maintenance.yml`** — rolt `node-maintenance` uit op `k8s_cluster:proxy:nextcloud:portainer`. jumpy houdt z'n eigen role (bewust niet getarget).
- **`ansible/playbooks/node-update.yml`** — drain-aware package-updates, één node tegelijk (`serial: 1`).
  - Play 1 (`k8s_cluster`): assert dat kubelet/kubeadm/kubectl op `apt-mark hold` staan → `kubectl drain` (via `delegate_to: localhost`) → `apt dist-upgrade` + autoremove → reboot-if-`/var/run/reboot-required` → `uncordon` → `kubectl wait --for=condition=Ready`.
  - Play 2 (`proxy:nextcloud:portainer`): plain `apt dist-upgrade` + reboot-if-required. Docker-containers komen terug via hun restart-policies.

### Why
- Scope-split (industrie-standaard): **security-patches unattended** (continu, geen reboot), maar **volledige upgrades + reboots georkestreerd**. Een kernel/runtime-bump met onbewaakte reboot op een live K8s-node killt workloads → daarom blijft de reboot drain-aware in een aparte playbook. De `apt-mark hold` op de K8s-packages (gezet door `kubeadm-install-packages.yml`) zorgt dat zowel unattended-upgrades als een routine dist-upgrade de clusterversie nooit meenemen; de assert in play 1 faalt-luid als die hold ontbreekt. Cluster-versie-hops blijven `kubeadm-upgrade.yml`.
- `unattended-upgrades` i.p.v. een zelfgebakken `apt upgrade` in bash: battle-tested, auditable, respecteert holds en de Ubuntu-security-origin out-of-the-box. Drain-aware auto-reboot (kured) komt op de roadmap zodra K8s op Proxmox-VMs draait.

### ⚠️ Operationeel — alléén vanaf jumpy draaien
- `node-update.yml` draait `kubectl drain/uncordon` via `delegate_to: localhost`. **alma's kubectl wijst naar productie** → dit playbook MOET vanaf jumpy (homelab-kubeconfig). Nooit vanaf alma.

### Verify after run (vanaf jumpy)
```bash
# syntax-check (geen host-contact)
cd ansible && ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/node-maintenance.yml playbooks/node-update.yml
# dry-run update op één worker
ansible-playbook -i inventory/hosts.yml playbooks/node-update.yml --limit node-02 --check
# na echte run: timer actief + node Ready
ansible -i inventory/hosts.yml node-02 -b -m command -a 'systemctl is-active node-maintenance.timer'
kubectl get nodes
```

### Open / vervolg
- Nog niet gedraaid tegen targets (geschreven op alma; uitrol gebeurt vanaf jumpy na review).
- Mogelijke consolidatie later: `jumpy-maintenance` herbouwen bovenop `node-maintenance` met een `nm_go_cache_clean`-toggle (nu lichte duplicatie, ~40 regels; bewust niet aangeraakt om de werkende jumpy-setup niet te migreren).

## 2026-06-01 — openwoo-acc TLS: HTTP-01 → DNS-01 (Cloudflare), intern-only

### Context / root cause
- `open.acc.westerweel.work` was thuis onbereikbaar. Diagnose: **geen Tailscale-probleem** (route `192.168.178.59/32` ok, ping + SSH werken). De hele `openwoo-acc`-stack op `.59` lag plat sinds 21 mei ~18:04. Oorzaak: het `letsencrypt`-volume is **leeg** (nooit een cert uitgegeven), waardoor `nginx-edge` op het ontbrekende `fullchain.pem` crashte (`[emerg]`, exit 1, crash-loop via `restart: unless-stopped`) en de stack uiteindelijk is `down` gehaald.

### Changed
- **`docker/openwoo-acc/docker-compose.yml`** — certbot-service van `certbot/certbot` (HTTP-01 webroot) → `certbot/dns-cloudflare` (DNS-01). Mount `./cloudflare.ini:ro` i.p.v. de webroot. Runbook-comments herschreven naar de DNS-01-commando's.
- **`ansible/playbooks/deploy-openwoo-acc.yml`** — nieuwe task genereert `/opt/openwoo-acc/cloudflare.ini` (mode 600, `no_log`) uit `CF_DNS_API_TOKEN` in `.env`; "next-step"-debug bijgewerkt naar DNS-01 i.p.v. publieke A-records + port-forward.
- **`docker/openwoo-acc/env.example`** — `CF_DNS_API_TOKEN` gedocumenteerd.
- **`.gitignore`** — `cloudflare.ini` toegevoegd (generated, bevat secret).

### Why
- Scope-keuze: site is **intern-only** (Tailscale + `/etc/hosts`), dus geen publieke DNS of router port-forward gewenst. HTTP-01 vereist publieke poort-80-bereikbaarheid → onbruikbaar. DNS-01 via Cloudflare bewijst zone-controle via TXT-record, sluit aan op het bestaande cluster-patroon (`*.westerweel.work`) en hergebruikt een token met `Zone:DNS:Edit` op `westerweel.work`. Token leeft in `/opt/openwoo-acc/.env` op de node (zelfde bron als de overige secrets), nooit in git.

### Verify after run
```bash
# vanaf .59: cert aanwezig + edge healthy
sudo docker compose -f /opt/openwoo-acc/docker-compose.yml ps
curl -sk -o /dev/null -w "%{http_code}\n" https://open.acc.westerweel.work/   # via /etc/hosts→Tailscale
```

## 2026-05-19 — openwoo-acc tenant (klant-d) — Caddy-bypass

### Added
- **`terraform/openwoo-acc/`** — VM 108 / `klant-d` / 192.168.178.59 / 6GB / 2c / 30GB. Clone van template 9000. Hardware-overrides terug in main.tf — token-perm-issue uit eerdere sessies was de werkelijke bpg-hang-oorzaak, niet de overrides (zie ADR-007 in claude-lxc-iac/docs).
- **`ansible/inventory/openwoo-acc-hosts.yml`** — group `openwoo_acc`, host `klant-d`, met per-host hostnames voor de twee vhosts.
- **`ansible/playbooks/deploy-openwoo-acc.yml`** — Docker installeren + compose stack deployen op `/opt/openwoo-acc/`.
- **`docker/openwoo-acc/`** — `docker-compose.yml` (7 services), `nginx-edge.conf` (publieke TLS + reverse proxy voor twee vhosts), `nginx-nextcloud.conf` (FastCGI naar nextcloud-fpm), `env.example`.
- **`ansible/inventory/group_vars/hypervisors.yml`** — `192.168.178.59/32` toegevoegd aan tailscale_advertise_routes.

### Why
- Klant wil OpenWoo-acc met **eigen NGINX als publieke voordeur** (Caddy bypass), Nextcloud-fpm + Postgres + Valkey-stack, plus de `woo-website-v2`-container ernaast. Domeinen `openwoo.acc.westerweel.work` (NC) en `open.acc.westerweel.work` (woo). Nextcloud op host-port 8080 voor directe interne toegang.
- TLS via Let's Encrypt HTTP-01 (certbot sidecar, profile=tools). Geen Cloudflare-token-sharing met Caddy.

### Open items (pre-go-live)
- Custom Nextcloud apps in `/var/www/html/custom_apps` (post-deploy via `occ app:enable`) — afwachten welke apps van Patrick Savalle.
- Woo-website-v2 env-vars: placeholder `NEXTCLOUD_URL` gezet, andere vereisten verifiëren met Patrick.
- DNS A-records: operator richt zelf in (Cloudflare).
- Router port-forward 80/443 → 192.168.178.59 (operator).
- Eerste certbot-run interactief vóór nginx-edge TLS-vhosts werken — runbook in compose comments.

### Verify after run
```bash
# vanaf jumpy
ssh ubuntu@192.168.178.59 'docker compose -f /opt/openwoo-acc/docker-compose.yml ps'
# verwacht: nginx-edge, nextcloud-nginx, nextcloud-fpm, postgres, valkey, woo-website
curl -sI http://192.168.178.59:8080 | head -1   # nginx-nc 200
curl -sI http://192.168.178.59:8081 | head -1   # woo-website
```

## 2026-05-16 — claude-lxc-iac ingeklapt in homelab als subfolder

### Added
- **`claude-lxc-iac/`** — Terraform + Ansible voor een single-purpose Claude Code dev LXC op Proxmox (VMID 210, IP .58, Ubuntu 24.04, agent user, Tailscale via tag:homelab-router). Was kort als standalone repo opgezet maar dat past niet bij de single-repo workflow van de homelab. Subdir-aanpak vastgelegd in `claude-lxc-iac/docs/decisions.md` (ADR-012).
- 6 Ansible-rollen (`base`, `ssh_hardening`, `tailscale`, `nodejs`, `claude_code`, `github_identity`) + plan/runbook/decisions docs + voorbeeld-configs voor `.env`, tfvars, inventory, group_vars, vault.

### Why
- Operator wil één repo, één push, één pull. Standalone-repo-ceremonie levert niks op bij één tailnet en één operator. Folder-scope blijft helder via `claude-lxc-iac/`-prefix in commits en file-paths.

### Verify after pull (jumpy)
```bash
cd ~/homelab/claude-lxc-iac
ls -la                # plan.md, runbook.md, decisions.md, terraform/, ansible/
```

Daarna pre-flight in `claude-lxc-iac/docs/runbook.md` § 0 (API-token, vault, tailscale auth-key, template download — laatste twee al gedaan op 2026-05-16).

## 2026-05-14 — nginx-proxy-lab toegevoegd (host-nginx + docker stack)

### Added
- **`terraform/nginx-proxy-lab/{main,variables,versions}.tf`** — single-VM module (vm 107, .57), kloont template 9000, geen hardware-overrides per het established pattern.
- **`ansible/inventory/nginx-proxy-lab-hosts.yml`** — inventory met group `nginx_proxy_lab`.
- **`ansible/playbooks/deploy-nginx-proxy-lab.yml`** — installeert native nginx + Docker engine (Docker's official APT-repo) + compose-plugin, deploy't `/opt/proxy-lab/docker-compose.yml`, start de stack, zet nginx default site uit zodat lab vanaf nul begint. Pre-task `wait_for_connection` voor cloud-init-readiness, `dpkg --configure -a` recovery.
- **`docker/proxy-lab/docker-compose.yml`** — twee sample-apps (`traefik/whoami` op 127.0.0.1:8081, `kennethreitz/httpbin` op 127.0.0.1:8082). Loopback-binding zodat host-nginx de enige publieke ingang is.
- **`~/Homelab/learning/nginx-docker-proxy-lab.md`** — lab-doc met provisioning-commands, de "ketting" browser→nginx→container, jouw werk (path- vs hostname-routing), proxy_set_header lessons, en tools-cheatsheet. Spoiler-vrij voor de nginx-config zelf.

### Why
- Tweede hands-on lab als opvolger van `nginx-lab`. Daar leerde je het bare-metal stack (nginx + php-fpm + mariadb + Nextcloud op één host). Hier leer je het patroon dat in echte productie veel vaker voorkomt: **host-nginx als publieke voordeur, applicaties in containers erachter**. Zelfde provisioning-pattern (template-clone via terraform, ansible voor packages + stack), zodat de hele "straat" reproduceerbaar blijft.

## 2026-05-14 — docs: VM-provisioning stack overzicht

### Added
- **`docs/07-vm-provisioning-stack.md`** — end-to-end uitleg van de vijf lagen (Proxmox template, Terraform, cloud-init, Ansible, Caddy), eenmalige setup-stappen (API-token rol, template-aanmaak), de bridging via cloud-init, en een troubleshooting-tabel voor first-run pijn. Bevat o.a. de exacte `TerraformProv`-rol + ACL commando's, want dat was de root cause van de "Still creating"-hang gisteren.

### Why
- Twee debug-sessies (2026-05-13/14) waren bijna volledig spelen-op-de-tast omdat het mentale model van wie-doet-wat tussen Proxmox, Terraform, cloud-init, en Ansible niet ergens centraal stond. CLAUDE.md schetst de pipeline maar niet de operationele inhoud (token-perms, lessons learned). Aparte doc voorkomt dat de volgende verse VM weer hetzelfde leertraject moet aflopen.

## 2026-05-14 — nginx-lab main.tf: alleen per-VM dingen overriden

### Changed
- **`terraform/nginx-lab/main.tf`** — `cpu`, `memory`, `operating_system` blocks verwijderd. Template `9000` levert die waardes al; ze ook in terraform zetten betekent dat bpg na de clone die properties opnieuw via `qmset` moet pushen. Dat is precies waar bpg's post-clone state-machine vastloopt — clones lukken, daarna stilte.

### Why
- Twee sessies lang debuggen (en bpg-upgrade 0.69 → 0.106) toonden hetzelfde patroon: `qmclone` OK, daarna geen `qmset`/`qmstart` operaties. Provider hangt in de centrale state-machine, vermoedelijk door een race tussen freshly-cloned VM-lock en de update-calls. Niet te fixen door provider-tuning omdat 't structureel met onze workflow conflicteert. Workaround die we *wel* in eigen hand hebben: minder werk post-clone door waardes die de template al levert, niet in terraform te zetten.

### Pattern voor sizing
- Andere CPU/memory/disk → aparte template (`9001 = larger`, etc.), niet per-VM tweaks. Hardware-shape blijft in template, per-VM-config (IP, user, key) blijft in IaC. Saait, auditeerbaar.

### Verify after apply
```
TF_LOG=INFO terraform apply
```
Verwacht: clones eindigen, daarna 1 `qmset` per VM voor ipconfig0/ciuser/sshkeys, daarna `qmstart`. Apply finisht in 3-4 min met `Apply complete!`.

## 2026-05-14 — bpg/proxmox provider upgrade 0.69 → 0.106

### Changed
- **`terraform/nginx-lab/versions.tf`** — provider constraint `~> 0.69` → `~> 0.106` (latest stable, 2026-05-06).

### Why
- Tijdens een schone destroy + apply test op 2026-05-14 hing terraform opnieuw 5+ minuten in `Still creating...` ondanks alle eerdere fixes. Proxmox-task-log toonde dat post-clone API-calls (memory, ipconfig0, ciuser, sshkeys) niet werden gepusht — bpg 0.69 had elk van die operaties als losse functie met eigen power-state-handling, wat in oudere versies regelmatig vastliep.
- Bpg #2508 (in 0.7x.x reeks) refactort dat: één centrale state-machine die alle wijzigingen tracked en pas aan het eind het VM-power-state corrigeert. Precies onze pijn.

### Breaking changes audit
Tussen 0.69 en 0.106 staan deze BREAKING items, geen raakt onze code:
- `lxc:` cpu.units default (we draaien VMs, geen containers)
- `vm:` VM datasources refactor (we gebruiken geen datasources)
- `vm:` `template` attribute no longer forces recreation (we zetten geen `template`)
- `vm:` operations needing shutdown fail when `reboot_after_update = false` (we zetten dat niet)
- `vm:` `initialization.dns.server` (singular) removed — we gebruiken `servers` (plural, current API)
- `node:` cpu_count consistency (we gebruiken geen node datasource)
- `proxmox_virtual_environment_download_file` overwrite default (niet in gebruik)
- `proxmox_virtual_environment_firewall_options` validation (niet in gebruik)

### Verify after pull
```bash
cd ~/homelab/terraform/nginx-lab
terraform init -upgrade            # haalt 0.106 binnen, vervangt 0.69
terraform plan                     # mag drift tonen vanwege state-mismatch, geen nieuwe resources
```

### Ook `terraform/nextcloud-vm/`
Beide modules bumped in dezelfde commit voor consistentie — als één module op `0.106` zit en de ander op `0.69` is dat een verborgen voetangel. **Let op bij `terraform plan` op `nextcloud-vm/`:** kans bestaat dat plan-drift toont op de live VMs (klant-a/b/c, proxy, portainer) door schema-veranderingen tussen 0.69 en 0.106. Inspecteer voor je `apply` doet — accepteer state-refresh, weiger ongewenste resource-recreate.

## 2026-05-14 — template als single source of truth voor disk-size

### Changed
- **Proxmox template `9000` op de host gegroeid van 3.5GB → 20.5GB** (`qm resize 9000 scsi0 +17G`). Affecteert alleen toekomstige clones — bestaande klant-a/b/c zijn full-clones en blijven 20GB.
- **`terraform/nginx-lab/main.tf`** — `disk { ... }` block verwijderd. Was een compensatie voor de te kleine template; nu overbodig en zou bij elke apply een nodeloze resize-call triggeren. Disk-grootte komt voortaan uit de template zelf.

### Why
- 3.5GB template was structureel te klein voor elke realistische Ubuntu-workload (apt liep direct vol). Compensatie via terraform werkte maar voegde een resize-API-call toe per clone — onnodig werk plus extra punt waar de bpg-provider kon haperen. Template-resize is een eenmalige actie, daarna heeft elke clone de juiste grootte by-default.

### Cosmetic note
- Template eindigt op 20.5GB ipv 20.0GB omdat `qm resize` alleen kan groeien (+17G op 3.5G = 20.5G). Shrinken zou ext4 corrumperen; recreaten van de template kost 15-20 min. Niet de moeite — clones krijgen wel exact 20GB.

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
