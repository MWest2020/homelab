#!/usr/bin/env bash
# Rehearsal: grow the wordsworth collection to production's volume count, so
# slot occupancy matches (31 Oct: the rehearsal had few volumes and could not
# show "10 of 10 full"). Production on 2026-11-05: 7 volumes with 001 on two
# servers, plus the filer log volume (000) on the all-in-one.
#   grow.sh [target-count]   default 7
set -euo pipefail
NS=seaweedfs-rehearsal; WANT=${1:-7}
count() { kubectl -n $NS exec deploy/seaweedfs -- sh -c 'printf "volume.list\n" | weed shell -master=localhost:9333 2>/dev/null' \
  | grep -oE "volume Id:[0-9]+, Size:[0-9]+, ReplicaPlacement:001, Collection:wordsworth" | grep -oE "Id:[0-9]+" | sort -u | wc -l; }
n=$(count)
while [ "$n" -lt "$WANT" ]; do
  # The master's HTTP API listens on the pod IP, not localhost.
  kubectl -n $NS exec deploy/seaweedfs -- sh -c 'wget -qO- "http://$(hostname -i):9333/vol/grow?collection=wordsworth&replication=001&count=1"' >/dev/null
  sleep 2; n=$(count)
done
echo "grown: $n wordsworth volumes with 001"
