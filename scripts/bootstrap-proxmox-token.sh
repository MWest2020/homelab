#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: installer
#
# scripts/bootstrap-proxmox-token.sh — maak de Terraform API-token + rol op een Proxmox-cluster.
#
# Maakt rol TerraformProv (minimaal nodig voor de bpg-provider na een clone — zonder
# VM.Audit hangt bpg in een 403-loop), user terraform@pve, een token (privsep uit),
# en zet de rol over / . Token-secret wordt 1x naar stdout geprint — kopieer 'm meteen.
#
# Tokens/users zijn CLUSTER-BREED: één keer draaien op een willekeurige node volstaat.
#
# Writes: Proxmox role/user/token/ACL config (in /etc/pve, cluster-wide). Print secret 1x.
# Idempotent: rol/user/ACL ja; token-creatie nee (bestaat 'ie al -> handmatig verwijderen
#             voor een nieuwe waarde: pveum user token remove terraform@pve terraform).
# Requires: root op een Proxmox-node, pveum.
#
# Usage:
#   ./bootstrap-proxmox-token.sh                                   # lokaal op een node
#   ssh root@100.120.76.22 'bash -s' < scripts/bootstrap-proxmox-token.sh   # vanaf jumpy

set -euo pipefail

readonly TF_USER="terraform@pve"
readonly TF_TOKEN="terraform"
readonly TF_ROLE="TerraformProv"
readonly TF_PRIVS="Datastore.AllocateSpace Datastore.AllocateTemplate Datastore.Audit \
Pool.Allocate SDN.Use Sys.Audit Sys.Console Sys.Modify User.Modify VM.Allocate VM.Audit \
VM.Clone VM.Config.CDROM VM.Config.Cloudinit VM.Config.CPU VM.Config.Disk VM.Config.HWType \
VM.Config.Memory VM.Config.Network VM.Config.Options VM.Migrate VM.Monitor VM.PowerMgmt"

main() {
  # Rol (idempotent: modify als 'ie al bestaat, anders add)
  if pveum role list 2>/dev/null | grep -qw "${TF_ROLE}"; then
    pveum role modify "${TF_ROLE}" -privs "${TF_PRIVS}"
  else
    pveum role add "${TF_ROLE}" -privs "${TF_PRIVS}"
  fi

  # User (idempotent)
  if ! pveum user list 2>/dev/null | grep -qw "${TF_USER}"; then
    pveum user add "${TF_USER}"
  fi

  # ACL over / (idempotent). Privsep-uit token erft deze user-rechten.
  pveum aclmod / -user "${TF_USER}" -role "${TF_ROLE}"

  # Token (NIET idempotent: secret is alleen bij aanmaak zichtbaar)
  if pveum user token list "${TF_USER}" 2>/dev/null | grep -qw "${TF_TOKEN}"; then
    echo "Token ${TF_USER}!${TF_TOKEN} bestaat al — secret niet opnieuw te tonen." >&2
    echo "Kwijt? Verwijder en run opnieuw: pveum user token remove ${TF_USER} ${TF_TOKEN}" >&2
    exit 0
  fi

  echo "=== TOKEN — kopieer de 'value' NU (wordt maar 1x getoond) ==="
  echo "Voor .env:  TF_VAR_proxmox_api_token=${TF_USER}!${TF_TOKEN}=<value>"
  echo
  pveum user token add "${TF_USER}" "${TF_TOKEN}" --privsep 0
}

main "$@"
