#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: entrypoint
#
# scripts/graceful-shutdown.sh — sluit de hele homelab tweefasig en parallel af.
#
# Draait vanaf een host die de stroomonderbreking zelf overleeft: de UPS-master
# (onbeheerd, via apcupsd — zie HOMELAB_SELF) of jumpy/alma (handmatig, bij een
# geplande onderbreking).
#
# Tweefasig, omdat px-01/02/03 een 3-node Proxmox-cluster zijn: zodra twee
# leden gehalt zijn is de derde niet meer quorate en blokkeert `qm shutdown`
# op "cluster not ready - no quorum?". Daarom eerst ALLE gasten op ALLE hosts
# omlaag (quorum nog intact), en pas daarna de hosts zelf.
#
#   fase 1  per host parallel: qm/pct shutdown van elke running gast, pollen
#           tot de host 0 gasten meldt
#   fase 2  pas na fase 1: shutdown -h now op alle hosts, parallel
#   fase 3  pollen met ping tot alles down is; dit script blijft zelf leven
#
# Draait het script OP een van de Proxmox-hosts (de UPS-master), zet dan
# HOMELAB_SELF op diens adres: die host doet fase 1 lokaal zonder ssh en wordt
# in fase 2 en 3 overgeslagen, zodat hij de rest kan afmaken.
#
# Parallel in plaats van serieel: serieel is worst case ~4,5 min per host,
# dus ~18 min voor vier hosts — meer dan de UPS-runtime bij vollast. Parallel
# is de totaaltijd die van de langzaamste host.
#
# Blijft een host in fase 1 met gasten zitten, dan gaat fase 2 tóch door: een
# host halten is altijd netter dan wachten tot de accu leeg is. Zet
# HOMELAB_STRICT=1 om in dat geval juist af te breken.
#
# Writes: zet gasten en Proxmox-hosts uit (graceful, geen datavernietiging).
#         Logt naar stdout; lockfile in "${HOMELAB_LOCK}".
# Idempotent: ja — al-onbereikbare hosts worden overgeslagen, en een tweede
#         gelijktijdige start stopt op de lock (apcupsd kan onbattery
#         herhaald afvuren).
# Requires: ssh + sleutel naar de hosts, ping, flock.
#
# Usage:
#   ./graceful-shutdown.sh --dry-run           # print wat het zou doen, muteert niets
#   ./graceful-shutdown.sh --phase1-only       # alleen gasten omlaag, hosts blijven up
#   ./graceful-shutdown.sh                     # volledige afsluiting
#   HOMELAB_VM_TIMEOUT=45 ./graceful-shutdown.sh
#   HOMELAB_HOSTS="100.120.76.22 100.89.39.27" ./graceful-shutdown.sh
#
# Als UPS-master, draaiend OP een Proxmox-host die zelf moet blijven leven
# (vereist root, want qm/pct lopen dan lokaal):
#   HOMELAB_SELF=100.94.15.50 \
#     HOMELAB_HOSTS="100.120.76.22 100.89.39.27 100.94.64.49 100.94.15.50" \
#     ./graceful-shutdown.sh
#
# Power-up daarna (handmatig): hosts aanzetten -> verify:
#   pvecm status            # 3 quorate
#   kubectl get nodes       # 6 Ready

set -euo pipefail

# px-01, px-02, px-03, proxmox-laptop (Tailscale-IP's). Voeg hosts toe die op
# dezelfde stroomgroep zitten en dus mee moeten.
readonly DEFAULT_HOSTS="100.120.76.22 100.89.39.27 100.94.64.49 100.94.15.50"

# Alle limieten env-tunable; hardcoded is niet testbaar.
readonly HOSTS_RAW="${HOMELAB_HOSTS:-$DEFAULT_HOSTS}"
readonly SSH_KEY="${HOMELAB_SSH_KEY:-${HOME}/.ssh/id_ed25519_homelab}"
readonly VM_TIMEOUT="${HOMELAB_VM_TIMEOUT:-90}"       # s, qm shutdown --timeout
readonly POLL_MAX="${HOMELAB_POLL_MAX:-30}"           # rondes fase 1
readonly POLL_INTERVAL="${HOMELAB_POLL_INTERVAL:-5}"  # s tussen rondes
readonly DOWN_POLL_MAX="${HOMELAB_DOWN_POLL_MAX:-60}" # rondes fase 3
readonly SSH_TIMEOUT="${HOMELAB_SSH_TIMEOUT:-8}"      # s ConnectTimeout
readonly STRICT="${HOMELAB_STRICT:-0}"
# Niet readonly: valt terug op TMPDIR als /var/lock niet schrijfbaar is (dat is
# zo bij een handmatige run als gewone gebruiker; onbeheerd draait dit als root).
LOCK="${HOMELAB_LOCK:-/var/lock/homelab-graceful-shutdown.lock}"

# De host waarop dit script zelf draait, als dat een Proxmox-host is (de
# UPS-master). Die doet fase 1 lokaal — geen ssh naar zichzelf — en wordt in
# fase 2 en 3 overgeslagen: hij moet blijven leven om de rest af te maken.
# Leeg = klassiek gedrag, alle hosts via ssh.
readonly SELF_HOST="${HOMELAB_SELF:-}"

readonly SSH_OPTS=(-o StrictHostKeyChecking=no -o IdentitiesOnly=yes
  -o BatchMode=yes -i "$SSH_KEY" -o "ConnectTimeout=${SSH_TIMEOUT}")

DRY_RUN=0
PHASE1_ONLY=0

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

err() {
  printf '%s error: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

usage() {
  sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

host_up() {
  ping -c1 -W2 "$1" >/dev/null 2>&1
}

# Het gast-afsluitprogramma, één kopie voor beide paden: via ssh op een remote
# host, of lokaal op de master. Leest zijn limieten uit de omgeving.
GUEST_SHUTDOWN_PROGRAM="$(
  cat <<'REMOTE'
set -u

running_vms() { qm list 2>/dev/null | awk 'NR>1 && $3=="running"{print $1}'; }
running_cts() { pct list 2>/dev/null | awk 'NR>1 && $2=="running"{print $1}'; }

vms="$(running_vms | tr '\n' ' ')"
cts="$(running_cts | tr '\n' ' ')"
echo "running VM's: ${vms:-geen}"
echo "running CT's: ${cts:-geen}"

if [ "$DRY_RUN" = "1" ]; then
  echo "dry-run: zou bovenstaande gasten afsluiten en dan pollen"
  exit 0
fi

for v in $vms; do qm shutdown "$v" --timeout "$VM_TIMEOUT" >/dev/null 2>&1 & done
for c in $cts; do pct shutdown "$c" >/dev/null 2>&1 & done
wait 2>/dev/null || true

i=0
while [ "$i" -lt "$POLL_MAX" ]; do
  left="$(( $(running_vms | wc -l) + $(running_cts | wc -l) ))"
  [ "$left" -eq 0 ] && { echo "alle gasten gestopt"; exit 0; }
  sleep "$POLL_INTERVAL"
  i=$((i + 1))
done

echo "nog $left gast(en) running na $((POLL_MAX * POLL_INTERVAL))s" >&2
exit 1
REMOTE
)"
readonly GUEST_SHUTDOWN_PROGRAM

# Fase 1 op één host: alle gasten omlaag, wachten tot de host 0 meldt.
# Schrijft de returncode naar "${statedir}/${host}.rc".
phase1_host() {
  local host="$1" statedir="$2" rc=0
  local -a env_prefix=(
    "VM_TIMEOUT=${VM_TIMEOUT}" "POLL_MAX=${POLL_MAX}"
    "POLL_INTERVAL=${POLL_INTERVAL}" "DRY_RUN=${DRY_RUN}"
  )

  if [[ -n "$SELF_HOST" && "$host" == "$SELF_HOST" ]]; then
    log "[$host] fase 1 LOKAAL (master, geen ssh)"
    env "${env_prefix[@]}" bash -s <<<"$GUEST_SHUTDOWN_PROGRAM" 2>&1 |
      sed "s/^/[$host] /" || rc=$?
  else
    if ! host_up "$host"; then
      log "[$host] onbereikbaar — overslaan"
      echo 0 >"${statedir}/${host}.rc"
      return 0
    fi
    log "[$host] fase 1: gasten afsluiten (timeout ${VM_TIMEOUT}s)"
    # shellcheck disable=SC2029  # bewust lokaal expanderen: limieten naar de remote shell
    ssh "${SSH_OPTS[@]}" root@"$host" "${env_prefix[*]} bash -s" \
      <<<"$GUEST_SHUTDOWN_PROGRAM" 2>&1 | sed "s/^/[$host] /" || rc=$?
  fi

  echo "$rc" >"${statedir}/${host}.rc"
  if [[ "$rc" -eq 0 ]]; then
    log "[$host] fase 1 klaar"
  else
    err "[$host] fase 1 niet schoon (rc=$rc)"
  fi
  return 0
}

# Fase 2 op één host: halt. De ssh-verbinding valt weg, dat is verwacht.
phase2_host() {
  local host="$1"

  if [[ -n "$SELF_HOST" && "$host" == "$SELF_HOST" ]]; then
    log "[$host] master — blijft up, wordt niet gehalt"
    return 0
  fi

  if ! host_up "$host"; then
    log "[$host] al down — overslaan"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[$host] dry-run: zou 'shutdown -h now' doen"
    return 0
  fi

  log "[$host] fase 2: shutdown -h now"
  ssh "${SSH_OPTS[@]}" root@"$host" 'shutdown -h now' >/dev/null 2>&1 || true
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1 ;;
      --phase1-only) PHASE1_ONLY=1 ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        err "onbekend argument: $1"
        usage >&2
        exit 2
        ;;
    esac
    shift
  done
  readonly DRY_RUN PHASE1_ONLY
}

main() {
  parse_args "$@"

  # Eén run tegelijk: apcupsd kan onbattery herhaald afvuren. Eerst testen of
  # het pad schrijfbaar is — een mislukte exec-redirect sloopt de shell.
  if ! : 2>/dev/null >>"$LOCK"; then
    if [[ -n "${HOMELAB_LOCK:-}" ]]; then
      err "lockfile niet schrijfbaar: $LOCK"
      exit 1
    fi
    LOCK="${TMPDIR:-/tmp}/homelab-graceful-shutdown.lock"
    log "standaard lockpad niet schrijfbaar — val terug op $LOCK"
    if ! : 2>/dev/null >>"$LOCK"; then
      err "lockfile niet schrijfbaar: $LOCK (zet HOMELAB_LOCK)"
      exit 1
    fi
  fi
  exec 9>>"$LOCK"
  if ! flock -n 9; then
    log "andere run is al bezig (lock: $LOCK) — stoppen"
    exit 0
  fi

  # Lokale fase 1 draait qm/pct op deze host; dat vraagt root.
  if [[ -n "$SELF_HOST" && "$DRY_RUN" -eq 0 && "${EUID}" -ne 0 ]]; then
    err "HOMELAB_SELF gezet maar niet als root — qm/pct lopen dan lokaal"
    exit 1
  fi

  local -a hosts
  read -r -a hosts <<<"$HOSTS_RAW"

  log "=== graceful shutdown homelab: ${#hosts[@]} host(s)$([[ -n "$SELF_HOST" ]] && echo " master=${SELF_HOST}")$([[ "$DRY_RUN" -eq 1 ]] && echo ' [DRY-RUN]') ==="

  local statedir
  statedir="$(mktemp -d)"
  # shellcheck disable=SC2064  # statedir nu vastpinnen, niet bij exit
  trap "rm -rf '$statedir'" EXIT

  # --- fase 1: alle gasten, alle hosts, parallel ---
  local h
  for h in "${hosts[@]}"; do
    phase1_host "$h" "$statedir" &
  done
  wait

  local failed=0
  for h in "${hosts[@]}"; do
    [[ "$(cat "${statedir}/${h}.rc" 2>/dev/null || echo 1)" -eq 0 ]] || failed=$((failed + 1))
  done

  if [[ "$failed" -gt 0 ]]; then
    err "$failed host(s) hebben fase 1 niet schoon afgerond"
    if [[ "$STRICT" -eq 1 ]]; then
      err "HOMELAB_STRICT=1 — fase 2 wordt NIET uitgevoerd"
      exit 1
    fi
    err "fase 2 gaat door: halten is netter dan wachten tot de accu leeg is"
  fi

  if [[ "$PHASE1_ONLY" -eq 1 ]]; then
    log "--phase1-only: hosts blijven up, klaar"
    [[ "$failed" -eq 0 ]] || exit 1
    exit 0
  fi

  # --- fase 2: hosts halten, parallel (geen gast meer, quorum irrelevant) ---
  for h in "${hosts[@]}"; do
    phase2_host "$h" &
  done
  wait

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "dry-run klaar — niets gemuteerd"
    exit 0
  fi

  # --- fase 3: wachten tot alles down is ---
  log "=== fase 3: wachten tot alle hosts down zijn ==="
  local i still_up=""
  for ((i = 0; i < DOWN_POLL_MAX; i++)); do
    still_up=""
    for h in "${hosts[@]}"; do
      [[ -n "$SELF_HOST" && "$h" == "$SELF_HOST" ]] && continue
      host_up "$h" && still_up+="$h "
    done
    [[ -z "$still_up" ]] && break
    sleep "$POLL_INTERVAL"
  done

  if [[ -n "$still_up" ]]; then
    err "nog bereikbaar na $((DOWN_POLL_MAX * POLL_INTERVAL))s: $still_up"
    exit 1
  fi

  log "==============================================="
  if [[ -n "$SELF_HOST" ]]; then
    log "   NODES DOWN  -  STROOM KAN ERAF"
    log "   (master ${SELF_HOST} blijft up)"
  else
    log "   ALLE NODES DOWN  -  STROOM KAN ERAF"
  fi
  log "==============================================="
}

main "$@"
