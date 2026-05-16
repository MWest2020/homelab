# Decisions — claude-lxc-iac

ADR-style: one entry per non-trivial call. Each entry lists what was chosen, why, what was rejected and why.

---

## ADR-001: Ubuntu 24.04 LTS as container OS

**Status**: accepted, 2026-05-14.

**Decision**: AlmaLinux 9 and Debian 12 were both real candidates; operator made the final call for **Ubuntu 24.04 LTS** during plan v2.

**Why**:
- Operator picked Ubuntu for *minimum friction*. Both upstream sources we depend on — Tailscale's `pkgs.tailscale.com/stable/ubuntu` and NodeSource's `deb.nodesource.com/node_20.x` — have first-class Ubuntu 24.04 (noble) repos with `signed-by` GPG hygiene. Zero EPEL workarounds, zero `dnf module` dances.
- The single-purpose nature of the container means OS-flavour cognitive load is paid once. Operator does not need RHCSA muscle memory on this box.
- 24.04 LTS lifecycle runs through 2034 (standard support to 2029, ESM to 2034) — comfortably beyond the operational horizon of this container.

**Rejected alternatives**:
- **AlmaLinux 9** — was the v1 plan default for consistency with the operator's main workstation. Real upside: same `dnf`, same SELinux, same `firewalld` mental model. Downside that broke the tie: Tailscale's RHEL packaging works fine but ergonomically slightly behind the Ubuntu side (subscription-manager / repo file vs. signed-by one-liner), and the operator wanted minimum friction over RHEL-discipline gains on what is, in effect, a single-app sandbox.
- **Debian 12** — also great choice, very similar story to Ubuntu in practice. Ubuntu won on familiarity with NodeSource's `nodistro` codename handling and on the operator's general daily-driver bias.

---

## ADR-002: LXC instead of full VM

**Status**: accepted, 2026-05-14.

**Decision**: Use a Proxmox **LXC container**, not a KVM virtual machine.

**Why**:
- Workload is one Node.js process (Claude Code) + occasional shell. No kernel-feature requirements that need VM-level isolation.
- Container start-up is sub-second, RAM-overhead near-zero vs. ~200MB for a baseline VM kernel, and `pct exec`-based recovery is fast when SSH ever goes sideways.
- Unprivileged LXC with explicit `/dev/net/tun` passthrough and `features = nesting` is fully sufficient for Tailscale userspace — no kernel-module install needed.

**Rejected alternatives**:
- **KVM VM** — would have been easier in only one respect: full kernel ownership, no `/dev/net/tun` config dance. Trade-offs (RAM, slower lifecycle, more layers between operator and process) didn't justify it for this use-case.
- **Docker on the Proxmox host** — explicitly out per the constraint "single-purpose container, no Docker". Also conflicts with Proxmox's container model.

---

## ADR-003: bpg/proxmox provider, not Telmate

**Status**: accepted, 2026-05-14.

**Decision**: Use **`bpg/proxmox`** version `~> 0.106`.

**Why**:
- Already in use across the rest of the homelab (`terraform/nextcloud-vm/`, `terraform/nginx-lab/`, `terraform/nginx-proxy-lab/`). Single provider for all VM/LXC work = single set of mental models, single token pattern, shared lessons (see `homelab/memory/project_proxmox_terraform_token_perms.md`).
- Active development cadence — releases roughly weekly through 2026; `0.106` (May 2026) contains the post-clone state-machine refactor (#2508) that hardened our existing VM-clone workflow.
- LXC support is first-class: `proxmox_virtual_environment_container` resource exposes initialization, network, disk, features, and device passthrough blocks.

**Rejected alternatives**:
- **Telmate/proxmox** — older, less maintained, schemas less consistent across resource types. Mixing providers means two GPG-key handling patterns, two state-file conventions, twice the lessons to relearn.

---

## ADR-004: OpenSSH (not Tailscale SSH) as the auth path

**Status**: accepted, 2026-05-14.

**Decision**: Standard `sshd`, hardened (key-only, no root, `AllowUsers agent`). Tailscale's built-in SSH (`tailscale up --ssh`) explicitly **off**.

**Why**:
- Auditability: every login attempt lands in `journald` / `auth.log` with the standard PAM/sshd story. No vendor-specific log format.
- Decoupling: Tailscale serves identity (you must be in the tailnet to reach the LXC) and routing (subnet routes). SSH serves authentication. Mixing both into Tailscale means a Tailscale-side ACL change can unintentionally affect login behaviour.
- Portability: the same SSH-key setup works equally over LAN (from jumpy) and over Tailscale (from alma). No `tailscale ssh` wrapper in muscle memory.
- Lockout-prevention is a known pattern: `wait_for` on port 22 after sshd reload, fail loudly before claiming the role done.

**Rejected alternatives**:
- **Tailscale SSH** — slick, but trades audit-trail clarity and adds vendor lock-in for one-token-revokes-all convenience. Convenience we don't need at the scale of one operator.

---

## ADR-005: Same GitHub account, dedicated machine SSH key (Scenario A)

**Status**: accepted, 2026-05-14.

**Decision**: The LXC uses the operator's existing GitHub account `mwest2020` for git auth, but with a **fresh ed25519 keypair** (`id_ed25519_github`) generated on the LXC itself. The key is **not** uploaded by automation; operator pastes the public half into github.com/settings/keys manually.

**Why**:
- One identity to manage: commits, PRs, comments all reflect `mwest2020`, matching personal repos under MWest2020.
- Machine-bound key gives us a unilateral revocation path: lose the LXC → remove that one key in GitHub settings → no other access surface compromised.
- Key generation on the LXC keeps the private half off the operator's primary workstation entirely — no rsync, no scp.
- Automated upload is **out of scope** per the spec (would require a PAT, complicates blast radius, and adds an API integration we don't otherwise need).

**Rejected alternatives**:
- **Scenario B: dedicated machine-account on GitHub** — would isolate this machine's commit identity completely. Overkill for personal-projects scope; complicates org membership and SSO; doubles the account-management work.
- **Reuse operator's existing GitHub SSH key** — would require copying a key off the primary workstation onto the LXC. Defeats the machine-bound-key advantage and creates a key-blast-radius problem.

---

## ADR-006: Reuse `tag:homelab-router`, no new Tailscale ACL surface

**Status**: accepted, 2026-05-14.

**Decision**: Tag the LXC with `tag:homelab-router`, the same tag used by the Proxmox host for subnet-routing. No new tag, no new ACL rule.

**Why**:
- Existing tailnet policy already has `autoApprovers.routes: 192.168.178.0/24 ← tag:homelab-router` (see `homelab/CHANGELOG.md` entry for 2026-05-14 Tailscale autoApprover setup).
- The LXC itself does not advertise routes — only the tag is shared, for membership grouping. The tag's blast radius is already governed by the existing policy.
- New tag = new ACL surface to design, document, and remember. Not justified by what this LXC does.

**Rejected alternatives**:
- **New `tag:dev` or `tag:claude-agent`** — cleaner namespace but pure cosmetic gain at the cost of more ACL maintenance.
- **No tag** — possible but loses the consistency in admin-console grouping.

---

## ADR-007: `/dev/net/tun` via provider-native passthrough first, manual `pct set` fallback documented

**Status**: provisional, 2026-05-14.

**Decision**: Use `device_passthrough { path = "/dev/net/tun" }` in the `proxmox_virtual_environment_container` resource (bpg `~> 0.106` exposes this). If a future provider release breaks the schema, fall back to the manual `pct set 210 -dev0 /dev/net/tun` documented in `docs/runbook.md` § 6.1.

**Why**:
- Tailscale's userspace daemon needs the tun device. Unprivileged LXC blocks devices by default.
- Provider-native is preferred: declarative, captured in state, no out-of-band drift.
- Fallback exists because the manual `pct set` path is well-documented in the Proxmox manual and survives schema churn.

**Verification of provider-native path is part of the first end-to-end run** (Definition of Done #1). If `terraform plan` shows an error on the device_passthrough block, this ADR moves to status: **rejected**, and we adopt the runbook fallback as the canonical path.

---

## ADR-008: SELinux — not applicable (Ubuntu base)

**Status**: noted, not a decision.

Ubuntu 24.04 uses AppArmor, not SELinux. No enforcing/permissive call to make. AppArmor profiles ship out-of-box for `tailscaled`, `sshd`; we don't override them. If a future role needs to relax or tighten an AppArmor profile, that decision gets its own ADR.

---

## ADR-012: Folded into homelab/ repo as subdir, not a standalone repo

**Status**: accepted, 2026-05-16.

**Decision**: `claude-lxc-iac/` lives as a subfolder of the existing `homelab/` git repo, not as a standalone repository.

**Why** (operator preference, accepted on the spot):
- Operator's actual workflow is single-repo: develop on alma, `git push`, `git pull` on jumpy. One push, one pull, all IaC arrives.
- A standalone repo would need its own GitHub remote + own clone command on every workstation. Pure ceremony for a single-operator setup.
- Auditability is not weakened: each commit on the homelab repo still cleanly delineates which subsystem changed via file paths. Mixed commits across subsystems can use scoped commit messages (`feat(claude-lxc):`).

**Rejected alternative**: separate `claude-lxc-iac` GitHub repo (initial plan v2 default, taken from the operator-pasted spec). The spec assumed cloud-style "one repo per system"; that doesn't fit a homelab where deployment context = "one operator, one tailnet, one repo of truth".

**Future-proofing**: if this folder ever grows to need its own release cadence / CI / external contributors, split it off via `git filter-repo` into its own repo. Cheap to do later, expensive to defend now.

---

## ADR-011: Per-usecase Proxmox API tokens, naam-scoped

**Status**: accepted, 2026-05-16.

**Decision**: Elke terraform-module (homelab VMs, nginx-lab, claude-lxc-iac, future projects) krijgt een **eigen Proxmox API-token** met een herkenbare scope-naam. Alle tokens delen de TerraformProv-rol over `/`; differentiatie zit in de naam en in per-repo `.env` files, niet in ACL-paden.

Namen die we vasthouden:
- `terraform@pve!terraform` — bestaand, voor homelab/ VMs (mag later herdoopt naar `homelab-vms` als je dat netter vindt; rename = nieuwe token + oude revoken).
- `terraform@pve!automation-lxc` — voor claude-lxc-iac/ (deze repo).
- Patroon voor toekomst: `terraform@pve!<purpose>` of `<purpose>-<scope>`.

**Why**:
- **Per-token revocation**: één gelekt of overbodig token uit te schakelen zonder andere pipelines plat te leggen.
- **Per-token audit-trail**: in Proxmox logs zie je welke "actor" wat deed. Bij één gedeelde token is dat een blob.
- **Per-token expiry**: kun je 90-daagse rotatie per project laten lopen zonder anderen te raken.
- **`.env`-eenvoud**: per repo één `.env`, daarin direct `PROXMOX_VE_API_TOKEN=<juiste-token>`. Geen suffix-bridges, geen `_LXC`-vs-niet-`_LXC` magie. Source de juiste `.env` per shell-context.

**Why niet tighter ACL** (rejected alternative):
- Proxmox-ACL ondersteunt geen `/vms/2*` wildcards. Per-VMID rows toevoegen is operationeel zwaar (elke nieuwe VM = ACL-update). Voor een single-operator homelab levert dat geen veiligheid die niveau-1 (naam-scoping) niet al doet.
- Mocht het threat-model later worden "een gelekte token mag niet alle VMs kunnen kapotmaken", dan komt level-2 in beeld — aparte ADR op dat moment.

**Trade-off geaccepteerd**:
- Wat een gelekt automation-lxc token wél kan: alle VMs en LXCs aanraken (TerraformProv op `/`). Mitigatie: korte token-expiry, monitoring van Proxmox audit-log, snelle revocation als ongebruikelijke calls verschijnen.

---

## ADR-010: Reuse existing homelab SSH key, no per-LXC login key

**Status**: accepted, 2026-05-16.

**Decision**: The login path to the LXC (operator → SSH → `agent` user) uses the operator's existing `~/.ssh/id_ed25519_homelab` keypair. We do NOT generate a dedicated `id_ed25519_agent_lxc` for this purpose.

(This is separate from the **GitHub identity** key generated *inside* the LXC by ADR-005 — that one is per-machine because it lives only on the LXC and is uploaded to GitHub.)

**Why** (operator's argument, accepted verbatim):

> Jumpy-compromise is the catastrophic scenario we plan against. Once jumpy is owned, every key on jumpy is owned — having `id_ed25519_homelab` and `id_ed25519_agent_lxc` side-by-side on the same host doesn't materially reduce blast-radius compared to one shared key. The complexity of managing per-target keys on a single jumpbox is not paid back by any real isolation gain.

- One key = one set of `authorized_keys` lines to audit.
- One key = one operator action when SSH'ing from a new tailnet device (load it into agent, done).
- If we ever do want per-machine keys, the natural boundary is per-WORKSTATION (alma's key vs. jumpy's key vs. tablet's key), not per-target. That's an orthogonal change and can happen later without revisiting this ADR.

**Rejected alternatives**:
- **Dedicated `id_ed25519_agent_lxc` on jumpy** — pre-plan-v2 suggestion. Real security gain ≈ zero given the threat model. Rejected.
- **Operator-supplied per-LXC key** — even thinner upside; would mean operator generates and tracks one ed25519 per LXC they ever provision. Not worth the cognitive overhead.

**Caveat**: if the threat model ever changes to "compromise of a single operator workstation must not grant LXC access" (e.g., the operator gets a phone they use for tailnet but want to exclude from this LXC), then per-host keys become valuable. Note in this ADR if that shift happens.

---

## ADR-009: Single-user bootstrap (no two-pass user-switching)

**Status**: accepted, 2026-05-14.

**Decision**: Ansible bootstraps as `root` (the cloud-init-injected SSH key lands in `root`'s `authorized_keys`). All roles run under `root` with `become_user` switching to `agent` for user-owned tasks (npm install, key generation, dotfile writes). Inventory does NOT switch `ansible_user` mid-playbook.

**Why**:
- One playbook run, one connection identity = simpler trace.
- `become_user` covers the "as the dev user" semantics cleanly for the half-dozen tasks that need it.
- The dev_user's `authorized_keys` is installed by the `base` role; from run 2 onward the operator may switch inventory `ansible_user` to `agent` for fully-rootless ops, but that's a manual choice, not playbook-driven.

**Rejected alternatives**:
- **Two-pass**: run bootstrap-as-root, then re-run rest-as-agent. Cleaner conceptually but adds a sequencing step that's easy to forget and a hidden dependency on first-pass success.
- **`ansible_user` swap via `meta: end_play` / `add_host`**: brittle, magic-by-runtime, hides behaviour from a reader of the inventory file.
