#!/usr/bin/env bash
# Node-loss drill for SeaweedFS only: cut every SeaweedFS pod on <node> off the
# network (NetworkPolicy, no rules = deny all in and out), as if the node were
# gone, without touching anything else on that node. A filer pod there is also
# taken out of its Deployment (relabelled), as Kubernetes would do after a real
# node loss, so a replacement starts elsewhere.
#   drill.sh <namespace> <node> isolate|heal
set -uo pipefail
NS=$1; NODE=$2; ACT=$3
pods() { kubectl -n "$NS" get pods -o wide --no-headers | awk -v n="$NODE" '$7==n && $1 ~ /^seaweedfs-/ {print $1}'; }
case $ACT in
isolate)
  for p in $(pods); do
    kubectl -n "$NS" label pod "$p" drill=isolated --overwrite >/dev/null
    case $p in seaweedfs-filer-*) kubectl -n "$NS" label pod "$p" app=seaweedfs-filer-drilled --overwrite >/dev/null ;; esac
    echo "isolated: $p"
  done
  kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: drill-node-loss, namespace: $NS}
spec:
  podSelector: {matchLabels: {drill: isolated}}
  policyTypes: [Ingress, Egress]
EOF
  ;;
heal)
  kubectl -n "$NS" delete networkpolicy drill-node-loss --ignore-not-found
  kubectl -n "$NS" delete pod -l app=seaweedfs-filer-drilled --ignore-not-found
  for p in $(kubectl -n "$NS" get pods -l drill=isolated -o name); do kubectl -n "$NS" label "$p" drill- >/dev/null; done
  echo "healed"
  ;;
esac
