#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: tool
#
# scripts/graceful-shutdown.sh — sluit de hele homelab gracefully af voor een stroomonderbreking.
#
# Draait vanaf jumpy (die blijft up). Per Proxmox-host: alle draaiende VM's + CT's netjes
# afsluiten (ACPI), wachten tot ze stopped zijn, dan de host halten. Daarna pollt 'ie tot
# alle hosts down zijn en geeft het sein "STROOM KAN ERAF". Power-up = hosts weer aanzetten;
# VM's met onboot=1 (de K8s-VM's 110-115) starten vanzelf.
#
# Writes: zet VM's/CT's + Proxmox-hosts uit (geen data-vernietiging; graceful).
# Idempotent: ja (al-down hosts worden overgeslagen).
# Requires: SSH (key id_ed25519_homelab) naar de hosts; ping.
#
# Usage:
#   ./graceful-shutdown.sh
#
# Power-up daarna (handmatig): hosts aanzetten -> verify:
#   pvecm status            # 3 quorate
#   kubectl get nodes       # 6 Ready (vanaf jumpy)

set -euo pipefail

# px-01, px-02, px-03, laptop-Proxmox (Tailscale-IP's). Voeg hier extra hosts toe die op
# dezelfde stroomgroep zitten (bv. agent-lxc's fysieke host) als die ook uit moeten.
readonly HOSTS=(100.120.76.22 100.89.39.27 100.94.64.49 100.94.15.50)
readonly SSH_OPTS=(-o StrictHostKeyChecking=no -o IdentitiesOnly=yes
  -i "${HOME}/.ssh/id_ed25519_homelab" -o ConnectTimeout=8)

shutdown_host() {
  local h="$1"
  if ! ping -c1 -W2 "$h" >/dev/null 2>&1; then
    echo "[$h] al onbereikbaar — overslaan"
    return 0
  fi
  echo "[$h] VM's + CT's gracefully afsluiten, daarna host halt..."
  ssh "${SSH_OPTS[@]}" root@"$h" 'bash -s' <<'REMOTE' || true
    for v in $(qm list | awk 'NR>1 && $3=="running"{print $1}'); do qm shutdown "$v" --timeout 120 & done
    for c in $(pct list 2>/dev/null | awk 'NR>1 && $2=="running"{print $1}'); do pct shutdown "$c" & done
    wait 2>/dev/null || true
    for _ in $(seq 1 30); do
      [ "$(qm list | awk 'NR>1 && $3=="running"' | wc -l)" -eq 0 ] || { sleep 5; continue; }
      break
    done
    shutdown -h now
REMOTE
}

main() {
  echo "=== Graceful shutdown homelab ==="
  for h in "${HOSTS[@]}"; do shutdown_host "$h"; done

  echo "=== Wachten tot alle hosts down zijn ==="
  for h in "${HOSTS[@]}"; do
    while ping -c1 -W2 "$h" >/dev/null 2>&1; do sleep 5; done
    echo "[$h] down"
  done

  echo
  echo "==============================================="
  echo "   ALLE NODES DOWN  -  STROOM KAN ERAF"
  echo "==============================================="
}

main "$@"
