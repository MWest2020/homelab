#!/usr/bin/env bash
# Is de accu van deze host nog een bruikbare UPS?
#
# De proxmox-laptop is de enige host met een accu, en daarmee de enige die een
# stroomonderbreking overleeft om de rest netjes af te sluiten
# (scripts/graceful-shutdown.sh, HOMELAB_SELF). Die rol staat of valt met een
# accu die genoeg lading heeft — en dat is precies het soort ding dat stil
# wegzakt.
#
# Gemeten op 2026-09-16: de accu stond op 28% en meldde "Charging", maar kreeg
# er in 45 seconden nul µAh bij, mét netstroom aanwezig. De cellen waren prima
# (98% van fabriekscapaciteit); het laden deed het niet. Niemand die het zag,
# want niemand kijkt in /sys.
#
#   ./scripts/check-battery.sh            # rapport, niet-nul bij een probleem
#   ./scripts/check-battery.sh --json     # voor een monitor
#
# Grenzen env-tunable; hardcoded is niet testbaar.
set -euo pipefail

readonly BAT="${HOMELAB_BAT:-/sys/class/power_supply/BAT0}"
readonly AC="${HOMELAB_AC:-/sys/class/power_supply/AC}"
readonly MIN_PCT="${HOMELAB_BAT_MIN_PCT:-40}"      # minder = te weinig marge
readonly MIN_HEALTH="${HOMELAB_BAT_MIN_HEALTH:-70}" # % van fabriekscapaciteit
readonly SETTLE="${HOMELAB_BAT_SETTLE:-45}"        # s om laden vast te stellen

lees() { cat "$BAT/$1" 2>/dev/null || echo ""; }

json=0
[ "${1:-}" = "--json" ] && json=1

if [ ! -d "$BAT" ]; then
  # Geen accu is geen fout: de meeste hosts hebben er geen. Maar het is wél een
  # reden om deze host niet als UPS-master te kiezen.
  [ "$json" = 1 ] && echo '{"battery":false}' || echo "accu: geen (deze host kan geen UPS-master zijn)"
  exit 0
fi

now=$(lees charge_now); full=$(lees charge_full); design=$(lees charge_full_design)
pct=$(lees capacity); status=$(lees status); online=$(cat "$AC/online" 2>/dev/null || echo "?")

health=""
if [ -n "$full" ] && [ -n "$design" ] && [ "$design" -gt 0 ] 2>/dev/null; then
  health=$(( full * 100 / design ))
fi

# Laadt hij echt? "Charging" in status is geen bewijs — dat stond er op
# 2026-09-16 ook terwijl er niets gebeurde. Meten is het verschil over tijd.
laadt="n.v.t."
if [ "$online" = "1" ] && [ -n "$now" ]; then
  sleep "$SETTLE"
  na=$(lees charge_now)
  if [ -n "$na" ] && [ "$na" -gt "$now" ] 2>/dev/null; then laadt="ja"; else laadt="NEE"; fi
fi

if [ "$json" = 1 ]; then
  printf '{"battery":true,"percent":%s,"health":%s,"status":"%s","ac":%s,"charging":"%s"}\n' \
    "${pct:-null}" "${health:-null}" "$status" "${online:-null}" "$laadt"
  exit 0
fi

echo "accu: ${pct}%  gezondheid ${health:-?}% van fabriekscapaciteit  status ${status}  netstroom ${online}  laadt ${laadt}"

fout=0
if [ -n "$pct" ] && [ "$pct" -lt "$MIN_PCT" ] 2>/dev/null; then
  echo "  TE WEINIG LADING  ${pct}% < ${MIN_PCT}% — te weinig marge om de homelab af te sluiten"
  fout=1
fi
if [ -n "$health" ] && [ "$health" -lt "$MIN_HEALTH" ] 2>/dev/null; then
  echo "  ACCU VERSLETEN    ${health}% < ${MIN_HEALTH}% van fabriekscapaciteit"
  fout=1
fi
if [ "$laadt" = "NEE" ] && [ -n "$pct" ] && [ "$pct" -lt 95 ] 2>/dev/null; then
  echo "  LAADT NIET        netstroom is aanwezig maar de lading loopt niet op"
  fout=1
fi
exit "$fout"
