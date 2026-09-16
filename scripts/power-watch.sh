#!/usr/bin/env bash
# Netstroom weg → homelab netjes afsluiten.
#
# Deze host (de proxmox-laptop) is de enige met een accu en daarmee de enige die
# een stroomonderbreking overleeft. Dat maakt hem de UPS-master: hij blijft leven
# en sluit de rest af met graceful-shutdown.sh (HOMELAB_SELF).
#
# Waarom de laptop-accu en geen apcupsd. De runbook ging uit van een UPS met
# apcupsd en een `onbattery`-event. Dat vraagt hardware die er niet is, en een
# daemon die op geen enkele host geïnstalleerd staat. De accu van deze laptop ís
# de UPS, en zijn eigen AC-status is het signaal: één bestand, geen daemon, geen
# extra hardware.
#
# Twee dingen die dit script bewust WEL doet:
#
#   - wachten (RESPIJT). Een flikkering van twee seconden mag de hele homelab
#     niet platleggen. Komt de stroom binnen de respijttijd terug, dan gebeurt er
#     niets en zegt het logboek dat.
#   - opnieuw kijken. Na het wachten wordt de AC-status opnieuw gelezen, niet
#     aangenomen.
#
# Draait als oneshot vanuit een udev-regel (90-homelab-power.rules), niet als
# poller: de kernel weet het meteen, en elke seconde pollen is een seconde accu.
#
#   ./scripts/power-watch.sh --dry-run    # print wat het zou doen
#   ./scripts/power-watch.sh              # echt
set -euo pipefail

readonly AC="${HOMELAB_AC:-/sys/class/power_supply/AC}"
readonly RESPIJT="${HOMELAB_POWER_GRACE:-90}"   # s wachten voor we het geloven
readonly HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SHUTDOWN="${HOMELAB_SHUTDOWN_SCRIPT:-$HERE/graceful-shutdown.sh}"
readonly SELF="${HOMELAB_SELF:-100.94.15.50}"   # deze host; zie graceful-shutdown.sh

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

log() { printf '%s power-watch: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }

netstroom() { cat "$AC/online" 2>/dev/null || echo "?"; }

nu=$(netstroom)
if [ "$nu" = "?" ]; then
  # Niet kunnen vaststellen is geen "alles in orde". Hier NIET afsluiten is de
  # juiste keuze — een onterechte afsluiting van de hele homelab is erger dan
  # een gemiste — maar het moet wél luid zijn. Niet-nul, zodat de unit op
  # "failed" komt en scripts/check-battery.sh en de timer-controle het zien.
  log "KAN AC-STATUS NIET LEZEN ($AC/online) — niet afgesloten, dit moet iemand nakijken"
  exit 1
fi
if [ "$nu" != "0" ]; then
  log "netstroom is aanwezig (online=$nu) — niets te doen"
  exit 0
fi

log "netstroom weg; ${RESPIJT}s respijt voordat we afsluiten"
if [ "$DRY_RUN" = 1 ]; then
  log "DRY-RUN: zou wachten en dan ${SHUTDOWN} draaien met HOMELAB_SELF=${SELF}"
  exit 0
fi

sleep "$RESPIJT"

opnieuw=$(netstroom)
if [ "$opnieuw" != "0" ]; then
  log "netstroom terug binnen de respijttijd (online=$opnieuw) — afsluiten afgeblazen"
  exit 0
fi

# Hoeveel accu is er nog? Puur om in het logboek te zetten: afsluiten doen we
# hoe dan ook, want wachten tot de accu leeg is is de slechtste uitkomst.
lading=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo "?")
log "netstroom nog steeds weg; accu ${lading}% — homelab afsluiten"

exec env HOMELAB_SELF="$SELF" "$SHUTDOWN"
