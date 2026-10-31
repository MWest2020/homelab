#!/usr/bin/env bash
# Full rehearsal in namespace seaweedfs-rehearsal: today's shape + synthetic
# data, then the runbook's cutover, the node-loss drill on the node with the
# old data volume, and heal. Uses the same cutover.sh / drill.sh as the live run.
set -uo pipefail
# Run from a directory holding these files plus ../cutover.sh, ../drill.sh,
# ../walk.py (as copied to jumpy), and old.rendered.yaml / new.rendered.yaml:
# kustomize of main and of the PR branch with the namespace and the Postgres
# host replaced (runbook, "Rehearsal").
cd "$(dirname "$0")"; N=seaweedfs-rehearsal; C="./cutover.sh $N new.rendered.yaml"
step() { echo "== $(date -u +%T) $*"; }
until ! kubectl get ns $N >/dev/null 2>&1; do sleep 3; done
rm -rf evidence-$N
kubectl create ns $N >/dev/null
kubectl -n $N create secret generic seaweedfs-s3-config --from-file=s3_config.json >/dev/null
kubectl -n $N create secret generic seaweedfs-db --type=kubernetes.io/basic-auth --from-literal=username=seaweedfs --from-literal=password="$(openssl rand -hex 24)" >/dev/null
kubectl apply -f old.rendered.yaml -f support.yaml >/dev/null
kubectl -n $N rollout status deploy/seaweedfs --timeout=240s >/dev/null && kubectl -n $N rollout status sts/seaweedfs-volume --timeout=240s >/dev/null
step seed; ./seed.sh
for s in baseline backup stop-old apply-new wait-masters wait-volumes load verify readall writetest; do
  step $s; $C $s > step.out 2>&1; rc=$?
  grep -vE "^(Waiting|partitioned|deployment \"|statefulset|service/|configmap/|persistentvolumeclaim/|deployment.apps/|statefulset.apps/)" step.out
  [ $rc -eq 0 ] || { echo "REHEARSAL STOP at $s (exit $rc)"; exit 1; }
done
NODE=$(kubectl -n $N get pod -l app=seaweedfs-volume-data -o jsonpath='{.items[0].spec.nodeName}')
step "drill on $NODE (node with the old data volume)"; ./drill.sh $N $NODE isolate
sleep 60
for m in 0 1 2; do echo "master-$m: $(kubectl -n $N exec seaweedfs-master-$m -- wget -qO- -T 5 http://localhost:9333/cluster/status 2>/dev/null | grep -oE '"(IsLeader|Leader)":[^,]*' | tr '\n' ' ')"; done
step "drill readall/writetest before filer restart"; $C readall; $C writetest
step "filer restart"; kubectl -n $N rollout restart deploy/seaweedfs-filer >/dev/null; kubectl -n $N rollout status deploy/seaweedfs-filer --timeout=180s >/dev/null; sleep 10
step "drill readall/writetest after filer restart"; $C readall; $C writetest
step heal; ./drill.sh $N $NODE heal; sleep 45
for m in 0 1 2; do echo "master-$m: $(kubectl -n $N exec seaweedfs-master-$m -- wget -qO- -T 5 http://localhost:9333/cluster/status 2>/dev/null | grep -oE '"(IsLeader|Leader)":[^,]*' | tr '\n' ' ')"; done
step "after heal"; $C readall; $C writetest; ./check.sh after-heal
step done
