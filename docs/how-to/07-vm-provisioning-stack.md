---
status: draft
last_reviewed: 2026-07-12
---

# 07 — VM-provisioning stack

End-to-end overzicht hoe een nieuwe VM op de homelab Proxmox bestaat van "niks" tot "draaiende app", inclusief welke tool verantwoordelijk is voor welke laag en wat eenmalig vs. herhaalbaar is.

## Landscape

```
┌─────────────────────────────────────────────────────────────────┐
│ PROXMOX HOST (192.168.178.10) — hypervisor                      │
│                                                                 │
│  ├─ Tailscale subnet-router                                     │
│  │  └─ /32-routes per VM-IP, NOOIT /24                          │
│  │     (zie ansible/playbooks/configure-tailscale-routes.yml)   │
│  │                                                              │
│  ├─ API-token  terraform@pve!terraform                          │
│  │  └─ rol TerraformProv (zie "Token permissions" onder)        │
│  │                                                              │
│  └─ Template VM 9000  ubuntu-24.04, 20.5GB, cloud-init enabled  │
│     ├─ VM 100 proxy        (Caddy reverse proxy)                │
│     ├─ VM 101-103 klant-a/b/c (Nextcloud tenants)               │
│     ├─ VM 104 portainer                                         │
│     └─ VM 105-106 nginx-lab-clean / nginx-lab-broken            │
└─────────────────────────────────────────────────────────────────┘
```

## De vijf lagen

| Laag | Tool | Wat het doet | Frequency |
|---|---|---|---|
| 1. Hardware-shape | Proxmox template (`qm`) | Welk OS + CPU/RAM/disk-size | Eenmalig per shape |
| 2. VM-creatie | Terraform (bpg/proxmox) | Clone template, set per-VM cloud-init waardes, start | Per VM (declaratief) |
| 3. First-boot config | cloud-init (in de VM) | IP toewijzen, ubuntu-user maken, SSH-key planten | Automatisch, eenmalig per VM |
| 4. App-config | Ansible | Software installen, services configureren | Per app, idempotent herhaalbaar |
| 5. External routing | Caddy (proxy-VM) | TLS-terminatie + hostname→tenant-IP | Per tenant, via Ansible-deploy |

**De "bridging" tussen Terraform en Ansible is cloud-init** — Terraform vertelt Proxmox welke cloud-init-waardes (`ipconfig0`, `ciuser`, `sshkeys`) op de cloud-init-CDROM moeten staan, en bij eerste boot leest de VM die CDROM en past ze toe op het live OS. Daarna is SSH bereikbaar en kan Ansible erover.

## Eenmalig op de Proxmox-host (laag 1)

### Template bouwen of resizen

Zie bestaande template 9000. Voor nieuwe shapes (bv. larger of GPU-enabled) — **nieuwe template aanmaken**, geen per-VM hardware-overrides in terraform (bpg's post-clone state-machine hangt anders):

```bash
qm clone 9000 9001 --full --name ubuntu-24.04-large
qm resize 9001 scsi0 +30G
qm set 9001 --memory 8192 --cores 4
qm template 9001
```

Daarna in terraform `clone.vm_id = 9001` voor de resources die deze shape gebruiken.

### API-token permissions

Zonder de juiste rol blijft `terraform apply` eeuwig "Still creating" hangen omdat bpg na de clone wil `GET /api2/json/nodes/proxmox/qemu/<id>/status/current` maar 403's krijgt op `VM.Audit`.

De rol `TerraformProv` heeft alle nodige perms. Toepassen op zowel user als token (anders snijdt token-privsep de perms weg):

```bash
pveum role add TerraformProv -privs "Datastore.AllocateSpace Datastore.AllocateTemplate Datastore.Audit Pool.Allocate SDN.Use Sys.Audit Sys.Console Sys.Modify User.Modify VM.Allocate VM.Audit VM.Clone VM.Config.CDROM VM.Config.Cloudinit VM.Config.CPU VM.Config.Disk VM.Config.HWType VM.Config.Memory VM.Config.Network VM.Config.Options VM.Migrate VM.Monitor VM.PowerMgmt"

pveum aclmod / -user  terraform@pve              -role TerraformProv
pveum aclmod / -token 'terraform@pve!terraform'  -role TerraformProv

# Verifieer — moet alle perms tonen incl. VM.Audit
pveum user permissions terraform@pve --path /vms
```

## Per VM via Terraform (laag 2)

Module `terraform/nginx-lab/` als referentie. Belangrijke principes:

- **Géén** `cpu`/`memory`/`disk`/`operating_system` blocks — die komen uit de template. Hardware-overrides in terraform → bpg hangt op post-clone `qmset`-calls.
- **Wel** `initialization { ip_config + user_account + dns }` — dat is per-VM-specifiek (IP, hostname, SSH-key).
- `started = true` — anders blokkeert bpg op state-mismatch met cloud-init's autostart.
- Token uit `.env` via `TF_VAR_proxmox_api_token`.

```bash
# vanaf jumpy
cd ~/homelab/terraform/<module>
source ../../.env
TF_LOG=DEBUG terraform apply 2>&1 | tee /tmp/tf.log    # DEBUG bij eerste runs
```

Verwacht ~3 min: clone → qmset (memory uitsluitend als afwijkend van template, ipconfig, ciuser, sshkeys) → cloudinit update → qmstart. Eindigt op `Apply complete!`.

## Per VM via cloud-init (laag 3)

Geen actie van jou. Wat er gebeurt op eerste boot van een gecloonde VM:

1. Bootloader detecteert cloud-init drive (`ide2: ...,media=cdrom`)
2. Cloud-init leest user-data: hostname, user, ssh-key, ip-config
3. Network-config wordt op `eth0` toegepast → VM heeft een IP
4. `ubuntu`-user met SSH-key in `~/.ssh/authorized_keys`
5. `sshd` start → externe SSH werkt

Duurt 30-90s na qmstart. SSH-ready check:

```bash
until ssh -o ConnectTimeout=5 ubuntu@<ip> true 2>/dev/null; do echo waiting; sleep 5; done
```

## Per app via Ansible (laag 4)

Per applicatie een playbook in `ansible/playbooks/`. Inventory in `ansible/inventory/`. Voorbeeld voor de nginx-lab:

```bash
cd ~/homelab/ansible
ansible-playbook -i inventory/nginx-lab-hosts.yml playbooks/deploy-nginx-lab.yml -vv
```

Playbook-conventies:
- Idempotent — re-runs zijn no-ops als de state al matcht
- `dpkg --configure -a` als pre-task om interrupted package-state te herstellen
- Variables in `inventory/group_vars/<group>.yml`

## External routing via Caddy (laag 5)

Caddy draait in een eigen VM (`proxy-01`, .50). `Caddyfile` in `docker/proxy/`. Per tenant een hostname die naar het juiste tenant-IP wijst. Deploy via:

```bash
ansible-playbook -i inventory/proxmox-hosts.yml playbooks/deploy-proxy.yml
```

## Wat van Tailscale komt

Per-VM IP-bereikbaarheid vanaf alma (en andere niet-LAN Tailscale-nodes) gaat via subnet-routing op de Proxmox-host. Adverteren van /32-routes is volledig ansible-managed; zie `ansible/playbooks/configure-tailscale-routes.yml` en `inventory/group_vars/hypervisors.yml`. Approval per route gebeurt eenmalig in de Tailscale admin-console.

## Troubleshooting first-run

| Symptoom | Diagnose | Fix |
|---|---|---|
| `terraform apply` blijft "Still creating" 5+ min | Token mist `VM.Audit` → `TF_LOG=DEBUG` toont 403's | Zie "API-token permissions" |
| Clone OK, maar `qm config <id>` toont geen `ipconfig0`/`ciuser`/`sshkeys` | bpg-hang stopte voor initialization push | Token-perms fixen, dan opnieuw |
| SSH `connection refused` (niet timeout) | VM is op, sshd komt nog | 30-60s wachten, cloud-init still seeding |
| SSH `connection timed out` | VM heeft geen IP of bridge/route fout | `qm config <id> \| grep ipconfig`; check Tailscale-routes vanaf alma |
| Ansible: `apt-mark manual ... No space left on device` | Template-disk te klein | Template resizen, zie laag 1 |
| Ansible: `dpkg was interrupted` | Vorige run brak halverwege af | Pre-task `dpkg --configure -a` herstelt — al in lab-playbook |

Voor de volledige debug-cookbook van een specifieke incident: zie de CHANGELOG-entries van 2026-05-13/14 (nginx-lab build).
