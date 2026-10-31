#!/usr/bin/env bash
# Rehearsal seed: bucket + 001 replication + 40 random objects over S3.
set -euo pipefail
NS=seaweedfs-rehearsal; S3=http://127.0.0.1:18333
kubectl -n $NS port-forward svc/seaweedfs 18333:8333 >/dev/null 2>&1 & PF=$!; trap 'kill $PF' EXIT; sleep 3
c() { curl -sf --aws-sigv4 "aws:amz:us-east-1:s3" --user rehearsalkey:rehearsalsecret "$@"; }
c -X PUT $S3/wordsworth >/dev/null
kubectl -n $NS exec deploy/seaweedfs -- sh -c 'printf "lock\nfs.configure -locationPrefix=/buckets/wordsworth/ -replication=001 -apply\nunlock\n" | weed shell -master=localhost:9333 >/dev/null 2>&1'
mkdir -p seed; rm -f seed/*
for i in $(seq 1 40); do
  sz=$(( (RANDOM * 37) % 300000 + 1000 )); [ $((i % 10)) -eq 0 ] && sz=$((9 * 1024 * 1024 + i))
  head -c $sz /dev/urandom > seed/obj$i
  dir=documents; [ $((i % 4)) -eq 0 ] && dir=redacted/r$i
  c -T seed/obj$i $S3/wordsworth/$dir/obj$i >/dev/null
done
echo seeded: $(ls seed | wc -l) objects, $(cat seed/* | wc -c) bytes
