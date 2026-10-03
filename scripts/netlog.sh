#!/usr/bin/env bash
# Netwerklogboek vanaf agent-lxc: elke 10 s één regel, zodat een wifi-/uplinkstoring
# achteraf aan te wijzen is (aanleiding 2026-09-28: vijf keer in vijf dagen vielen alle
# Cloudflare-tunnels tegelijk om; de switch van het cluster hangt aan een wifi-extender).
#
# Kolommen (TSV, UTC): tijd, router_ms, node01_ms, extern_ms, dns_router_ms, https_ms
# Een leeg veld betekent "geen antwoord binnen de time-out" — dat is de storing.
# https_ms wordt eens per minuut gemeten, anders leeg.
set -u
DIR=${NETLOG_DIR:-$HOME/netlog}
ROUTER=${NETLOG_ROUTER:-192.168.178.1}
NODE=${NETLOG_NODE:-192.168.178.205}      # node-01, achter de switch aan de extender
EXTERN=${NETLOG_EXTERN:-9.9.9.9}          # Quad9 (Zwitserland)
DNSNAAM=${NETLOG_DNSNAAM:-sidn.nl}
URL=${NETLOG_URL:-https://www.sidn.nl/}
mkdir -p "$DIR"

ping_ms() {  # één ping, rtt in ms of leeg
    ping -n -c1 -W2 "$1" 2>/dev/null | sed -n 's/.*time=\([0-9.]*\) ms.*/\1/p'
}
dns_ms() {
    dig +time=2 +tries=1 @"$ROUTER" "$DNSNAAM" A 2>/dev/null | sed -n 's/^;; Query time: \([0-9]*\) msec/\1/p'
}
https_ms() {
    curl -s -o /dev/null -m 5 -w '%{time_total}' "$URL" 2>/dev/null | awk '$1>0 {printf "%.0f", $1*1000}'
}

n=0
while true; do
    t=$(date -u +%FT%TZ)
    f="$DIR/$(date -u +%F).tsv"
    [ -f "$f" ] || printf 'tijd\trouter_ms\tnode01_ms\textern_ms\tdns_router_ms\thttps_ms\n' > "$f"
    h=""; [ $((n % 6)) -eq 0 ] && h=$(https_ms)
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$t" "$(ping_ms "$ROUTER")" "$(ping_ms "$NODE")" \
        "$(ping_ms "$EXTERN")" "$(dns_ms)" "$h" >> "$f"
    # Eens per 10 min de regels van de DaemonSet netlog (cluster-config/infra/netlog)
    # binnenhalen: podlogs verdwijnen bij een herstart van pod of node, en dat is
    # precies het moment waar het om gaat. Altijd de laatste 3 uur, ontdubbeld: jumpy
    # is via Tailscale bereikbaar, dus tijdens een internetstoring mislukt het ophalen
    # (2026-10-03 00:18, tien minuten zonder internet, gat in het clusterlog). Met
    # alleen "sinds 11 min" werd dat gat nooit meer gevuld. Elke regel gaat naar het
    # bestand van zijn eigen dag.
    if [ $((n % 60)) -eq 0 ]; then
        ssh -o BatchMode=yes -o ConnectTimeout=5 jumpy \
            'kubectl -n netlog logs -l app=netlog --since=3h --tail=-1 --max-log-requests=10' \
            2>/dev/null | awk -v d="$DIR" '/^20[0-9][0-9]-/ {print >> (d "/cluster-" substr($1,1,10) ".log")}'
        for c in "$DIR/cluster-$(date -u +%F).log" "$DIR/cluster-$(date -u -d yesterday +%F).log"; do
            [ -f "$c" ] && sort -u -o "$c" "$c"
        done
    fi
    # Eens per uur: logs ouder dan 30 dagen weg.
    [ $((n % 360)) -eq 0 ] && find "$DIR" \( -name '*.tsv' -o -name '*.log' \) -mtime +30 -type f -exec rm -f {} + 2>/dev/null
    n=$((n + 1))
    sleep 10
done
