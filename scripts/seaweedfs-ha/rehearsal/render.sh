#!/usr/bin/env bash
# Render today's shape (main) and the HA shape (PR branch) for the rehearsal:
# namespace seaweedfs -> seaweedfs-rehearsal, service DNS likewise, and the
# filer store pointed at the throwaway rehearsal-pg (no TLS) instead of CNPG.
#   render.sh <checkout-of-main> <checkout-of-pr-branch>   (writes ./old.rendered.yaml ./new.rendered.yaml)
set -euo pipefail
fix() { sed -E -e 's/^(\s*)namespace: seaweedfs$/\1namespace: seaweedfs-rehearsal/' \
               -e 's/\.seaweedfs\.svc/.seaweedfs-rehearsal.svc/g' \
               -e 's/homelab-pg-rw\.cnpg-database\.svc\.cluster\.local/rehearsal-pg.seaweedfs-rehearsal.svc.cluster.local/' \
               -e 's/sslmode = "require"/sslmode = "disable"/'; }
kubectl kustomize "$1/cluster-config/infra/seaweedfs" | fix > old.rendered.yaml
kubectl kustomize "$2/cluster-config/infra/seaweedfs" | fix > new.rendered.yaml
! grep -nE 'namespace: seaweedfs$|\.seaweedfs\.svc|cnpg-database' old.rendered.yaml new.rendered.yaml
echo "rendered: $(grep -c '^kind:' old.rendered.yaml) old, $(grep -c '^kind:' new.rendered.yaml) new objects"
