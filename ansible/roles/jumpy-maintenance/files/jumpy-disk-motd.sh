#!/bin/sh
# Shows disk usage for / at interactive login. Silent below 70%.

case $- in
  *i*) ;;
  *) return 0 ;;
esac

_usage=$(df -h / | awk 'NR==2 {print $5 " used (" $3 " of " $2 ", " $4 " free)"}')
_pct=$(df / | awk 'NR==2 {gsub("%",""); print $5}')

if [ "$_pct" -ge 85 ]; then
  printf '\n\033[1;31m[jumpy disk]\033[0m %s — run: sudo systemctl start jumpy-maintenance\n\n' "$_usage"
elif [ "$_pct" -ge 70 ]; then
  printf '\n\033[1;33m[jumpy disk]\033[0m %s\n\n' "$_usage"
fi

unset _usage _pct
