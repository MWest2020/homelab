#!/usr/bin/env bash
# Rehearsal check: GET every seeded object over S3 and compare md5 with the
# local seed; then write and read back one new object. Prints counts only.
set -uo pipefail
NS=seaweedfs-rehearsal; S3=http://127.0.0.1:18333; TAG=${1:-check}
kubectl -n $NS port-forward svc/seaweedfs 18333:8333 >/dev/null 2>&1 & PF=$!; trap 'kill $PF' EXIT; sleep 3
c() { curl -sf --max-time 20 --aws-sigv4 "aws:amz:us-east-1:s3" --user rehearsalkey:rehearsalsecret "$@"; }
ok=0; bad=0
for f in seed/*; do i=${f#seed/obj}; dir=documents; [ $((i % 4)) -eq 0 ] && dir=redacted/r$i
  if [ "$(c $S3/wordsworth/$dir/obj$i | md5sum | cut -d' ' -f1)" = "$(md5sum < $f | cut -d' ' -f1)" ]; then ok=$((ok+1)); else bad=$((bad+1)); fi
done
head -c 50000 /dev/urandom > seed-$TAG.bin
w=FAIL; c -T seed-$TAG.bin $S3/wordsworth/writes/$TAG >/dev/null && [ "$(c $S3/wordsworth/writes/$TAG | md5sum)" = "$(md5sum < seed-$TAG.bin)" ] && w=OK
n=$(c "$S3/wordsworth?list-type=2&max-keys=1000" | grep -o "<Key>" | wc -l)
echo "$TAG: read ok=$ok bad=$bad; write+readback=$w; listed keys=$n"
