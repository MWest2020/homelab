#!/usr/bin/env bash
# SeaweedFS all-in-one -> 3 Raft masters + 3 volume servers + 2 filers on
# Postgres (wordsworth#193 task 1.2). The core of runbook
# seaweedfs-ha-migration.md, step by step; each step stops on failure.
#   cutover.sh <namespace> <rendered-target.yaml> <step>
# steps: baseline | backup | stop-old | apply-new | wait-masters |
#        wait-volumes | load | verify | readall | writetest
# Runs on jumpy; writes its evidence into ./evidence-<namespace>/.
set -euo pipefail
NS=$1; TARGET=$2; STEP=$3
E=evidence-$NS; mkdir -p "$E"
WALK=$(dirname "$0")/walk.py
shell() { kubectl -n "$NS" exec "$1" -- sh -c "printf '$2\n' | weed shell -master=${3:-localhost:9333} ${4:-} 2>&1"; }
# vols <pod>: "copies Id:N, ReplicaPlacement:P, Collection:C" per volume id.
vols() { shell "$1" "volume.list" | grep -oE "volume Id:[0-9]+, Size:[0-9]+, ReplicaPlacement:[0-9]+, Collection:[^,]*" | sed -E 's/ Size:[0-9]+,//' | sort | uniq -c | sort -k2V; }
walk_to() { # walk_to <pod-or-deploy> <outfile>
  local port=$((20000 + RANDOM % 10000))
  kubectl -n "$NS" port-forward "$1" $port:8888 >/dev/null 2>&1 & local pf=$!
  sleep 4; python3 "$WALK" http://127.0.0.1:$port | sort > "$2"; kill $pf
}
case $STEP in
baseline)
  walk_to deploy/seaweedfs "$E/before-chunks.tsv"
  vols deploy/seaweedfs > "$E/before-volumes.txt"
  shell deploy/seaweedfs "fs.configure" > "$E/before-fsconfigure.txt"
  echo "baseline: $(wc -l < "$E/before-chunks.tsv") files, $(awk -F'\t' '{s+=$2} END{print s}' "$E/before-chunks.tsv") bytes, $(wc -l < "$E/before-volumes.txt") volume ids"
  ;;
backup)
  P=$(kubectl -n "$NS" get pod -l app=seaweedfs -o jsonpath='{.items[0].metadata.name}')
  shell "$P" "fs.meta.save -o /tmp/meta.meta" | tail -2
  kubectl -n "$NS" exec "$P" -- cat /tmp/meta.meta > "$E/meta.meta"
  # Seal: fs.meta.load (4.39) can lose the last record when it is a file (its
  # goroutine races the shell's exit). Append a copy of the last directory
  # record; a directory record makes the loader wait for all pending files,
  # and re-creating an existing directory is an idempotent upsert.
  python3 - "$E/meta.meta" "$E/meta.sealed.meta" <<'PY'
import struct, sys
b = open(sys.argv[1], 'rb').read(); i = 0; recs = []
while i < len(b):
    n = struct.unpack('>I', b[i:i+4])[0]; recs.append(b[i:i+4+n]); i += 4 + n
# FullEntry: field 1 dir, field 2 entry; Entry: field 2 is_directory.
def is_dir(r):
    m = r[4:]; j = 0
    while j < len(m):
        key = m[j]; j += 1; f, t = key >> 3, key & 7
        ln = 0; s = 0
        while True:
            x = m[j]; j += 1; ln |= (x & 0x7f) << s; s += 7
            if x < 0x80: break
        if f == 2:
            e = m[j:j+ln]; k = 0
            while k < len(e):
                key2 = e[k]; k += 1; f2, t2 = key2 >> 3, key2 & 7
                if t2 == 0:
                    v = 0; s = 0
                    while True:
                        x = e[k]; k += 1; v |= (x & 0x7f) << s; s += 7
                        if x < 0x80: break
                    if f2 == 2: return v == 1
                elif t2 == 2:
                    l2 = 0; s = 0
                    while True:
                        x = e[k]; k += 1; l2 |= (x & 0x7f) << s; s += 7
                        if x < 0x80: break
                    k += l2
                elif t2 == 5: k += 4
                elif t2 == 1: k += 8
            return False
        j += ln
    return False
dirs = [r for r in recs if is_dir(r)]
open(sys.argv[2], 'wb').write(b + dirs[-1])
print(f"backup: {len(recs)} records, {sum(map(is_dir, recs))} directories; last record is a {'directory' if is_dir(recs[-1]) else 'file'}; sealed")
PY
  sha256sum "$E/meta.meta" "$E/meta.sealed.meta"
  ;;
stop-old)
  kubectl -n "$NS" scale deploy/seaweedfs --replicas=0
  kubectl -n "$NS" wait --for=delete pod -l app=seaweedfs --timeout=120s || true
  echo "stop-old: all-in-one at 0 replicas (its volume, leveldb and master state untouched)"
  ;;
apply-new)
  kubectl apply -f "$TARGET"
  ;;
wait-masters)
  kubectl -n "$NS" rollout status sts/seaweedfs-master --timeout=300s
  for i in $(seq 1 30); do
    st=$(kubectl -n "$NS" exec seaweedfs-master-0 -- wget -qO- http://localhost:9333/cluster/status 2>/dev/null || true)
    echo "$st" | grep -q '"Leader":"seaweedfs-master' && break; sleep 5
  done
  echo "$st" > "$E/masters-status.json"; echo "wait-masters: $st"
  echo "$st" | grep -q '"Leader":"seaweedfs-master' || { echo "STOP: no Raft leader"; exit 1; }
  ;;
wait-volumes)
  kubectl -n "$NS" rollout status deploy/seaweedfs-volume-data --timeout=300s
  kubectl -n "$NS" rollout status sts/seaweedfs-volume --timeout=300s
  for i in $(seq 1 24); do
    vols seaweedfs-master-0 > "$E/after-volumes.txt"
    # Every baseline volume must be back with the same number of copies; new
    # volumes (e.g. a filer log volume grown since) are allowed and listed.
    [ -z "$(comm -23 <(sort "$E/before-volumes.txt") <(sort "$E/after-volumes.txt"))" ] && break; sleep 5
  done
  missing=$(comm -23 <(sort "$E/before-volumes.txt") <(sort "$E/after-volumes.txt"))
  [ -z "$missing" ] || { echo "STOP: baseline volumes missing or with fewer copies:"; echo "$missing"; exit 1; }
  echo "wait-volumes: all $(wc -l < "$E/before-volumes.txt") baseline volume ids back with the same copies"
  comm -13 <(sort "$E/before-volumes.txt") <(sort "$E/after-volumes.txt") | sed 's/^/  new since baseline: /'
  ;;
load)
  kubectl -n "$NS" rollout status deploy/seaweedfs-filer --timeout=300s
  F=$(kubectl -n "$NS" get pod -l app=seaweedfs-filer -o jsonpath='{.items[0].metadata.name}')
  kubectl -n "$NS" cp "$E/meta.sealed.meta" "$F:/tmp/meta.sealed.meta"
  shell "$F" "fs.meta.load /tmp/meta.sealed.meta" seaweedfs-master:9333 "-filer=localhost:8888" | tail -2
  ;;
verify)
  for F in $(kubectl -n "$NS" get pod -l app=seaweedfs-filer -o jsonpath='{.items[*].metadata.name}'); do
    walk_to "pod/$F" "$E/after-chunks-$F.tsv"
    diff -q "$E/before-chunks.tsv" "$E/after-chunks-$F.tsv" >/dev/null && echo "verify $F: identical ($(wc -l < "$E/after-chunks-$F.tsv") files, path+size+md5+chunks)" || { echo "STOP: $F differs"; diff "$E/before-chunks.tsv" "$E/after-chunks-$F.tsv" | head -5 | cut -c1-120; exit 1; }
  done
  F=$(kubectl -n "$NS" get pod -l app=seaweedfs-filer -o jsonpath='{.items[0].metadata.name}')
  shell "$F" "fs.configure" seaweedfs-master:9333 "-filer=localhost:8888" > "$E/after-fsconfigure.txt"
  diff "$E/before-fsconfigure.txt" "$E/after-fsconfigure.txt" >/dev/null && echo "verify: filer.conf (replication 001 rule) identical" || { echo "STOP: filer.conf differs"; exit 1; }
  ;;
readall)
  # GET every file through a filer (filer -> volume servers, the read path
  # S3 uses) and compare md5 (or size, for multipart files without one).
  port=$((20000 + RANDOM % 10000))
  kubectl -n "$NS" port-forward deploy/seaweedfs-filer $port:8888 >/dev/null 2>&1 & pf=$!; sleep 4
  python3 - "$E/before-chunks.tsv" $port <<'PY'
import hashlib, sys, time, urllib.parse, urllib.request
ok = bad = 0; t = time.time()
for line in open(sys.argv[1]):
    path, size, md5 = line.rstrip("\n").split("\t")[:3]
    try:
        body = urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[2]}{urllib.parse.quote(path)}", timeout=30).read()
        good = len(body) == int(size) and (md5 == "-" or hashlib.md5(body).hexdigest() == md5)
    except Exception:
        good = False
    ok += good; bad += not good
print(f"readall: ok={ok} bad={bad} in {time.time() - t:.0f}s")
sys.exit(1 if bad else 0)
PY
  rc=$?; kill $pf; [ $rc -eq 0 ] || { echo "STOP: readall failed"; exit 1; }
  ;;
writetest)
  # Write, read back and delete one file outside the buckets (assign + a 001
  # write on two volume servers + read + delete). Prints pass/fail only.
  port=$((20000 + RANDOM % 10000)); f=$(mktemp)
  kubectl -n "$NS" port-forward deploy/seaweedfs-filer $port:8888 >/dev/null 2>&1 & pf=$!; sleep 4
  head -c 200000 /dev/urandom > "$f"; key=/migration-check/$(date +%s)
  r=FAIL
  curl -sf --max-time 30 -F "file=@$f" "http://127.0.0.1:$port$key" >/dev/null \
    && [ "$(curl -sf --max-time 30 "http://127.0.0.1:$port$key" | md5sum)" = "$(md5sum < "$f")" ] \
    && curl -sf --max-time 30 -X DELETE "http://127.0.0.1:$port$key" >/dev/null && r=OK
  kill $pf; rm -f "$f"; echo "writetest: $r"; [ $r = OK ]
  ;;
*) echo "unknown step $STEP"; exit 2 ;;
esac
