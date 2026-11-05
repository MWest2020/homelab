#!/bin/bash
# Usage (from jumpy): bash scripts/key-backups/restore-test.sh
# Restores the newest document_keys dump and OpenBao snapshot from the bucket
# wordsworth-key-backups into a throwaway namespace, and unwraps a value that
# production wraps now. Read-only on production. Runbook: key-backups.md.
# Restore test for the key backups; runs on jumpy. Prints no key material.
set -euo pipefail
NS=keys-restore-test
kubectl create ns $NS >/dev/null
trap 'kubectl delete ns $NS --wait=false >/dev/null 2>&1 || true' EXIT
AK=$(kubectl -n wordsworth get secret wordsworth-s3 -o jsonpath='{.data.WORDSWORTH_S3_ACCESS_KEY}' | base64 -d)
SK=$(kubectl -n wordsworth get secret wordsworth-s3 -o jsonpath='{.data.WORDSWORTH_S3_SECRET_KEY}' | base64 -d)
kubectl -n $NS create secret generic s3 --from-literal=AWS_ACCESS_KEY_ID="$AK" --from-literal=AWS_SECRET_ACCESS_KEY="$SK" >/dev/null
cat <<YAML | kubectl -n $NS apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata: { name: restore }
spec:
  restartPolicy: Never
  volumes: [ { name: b, emptyDir: {} }, { name: pg, emptyDir: {} }, { name: bao, emptyDir: {} } ]
  initContainers:
    - name: fetch
      image: amazon/aws-cli:2.31.18
      command: ["/bin/sh","-c"]
      args:
        - |
          set -eu
          S3="aws --endpoint-url http://seaweedfs.seaweedfs.svc.cluster.local:8333 s3"
          d=\$(\$S3 ls s3://wordsworth-key-backups/document_keys/ | awk '{print \$4}' | grep '\.dump$' | sort | tail -1)
          o=\$(\$S3 ls s3://wordsworth-key-backups/openbao/ | awk '{print \$4}' | grep '\.snap$' | sort | tail -1)
          for k in "document_keys/\$d" "document_keys/\$d.sha256" "document_keys/\$d.rows" "openbao/\$o" "openbao/\$o.sha256"; do \$S3 cp "s3://wordsworth-key-backups/\$k" /b/ --only-show-errors; done
          cd /b && for f in "\$d" "\$o"; do [ "\$(sha256sum "\$f" | cut -d' ' -f1)" = "\$(cat "\$f.sha256")" ] && echo "sha256 ok: \$f" || { echo "sha256 MISMATCH: \$f"; exit 1; }; done
          cp "\$d" /b/keys.dump; cp "\$o" /b/bao.snap; cp "\$d.rows" /b/keys.rows
      envFrom: [ { secretRef: { name: s3 } } ]
      env: [ { name: AWS_DEFAULT_REGION, value: us-east-1 }, { name: HOME, value: /tmp } ]
      volumeMounts: [ { name: b, mountPath: /b } ]
  containers:
    - name: pg
      image: postgres:17.10-alpine
      env: [ { name: POSTGRES_PASSWORD, value: throwaway }, { name: POSTGRES_DB, value: restore } ]
      volumeMounts: [ { name: b, mountPath: /b }, { name: pg, mountPath: /var/lib/postgresql/data } ]
    - name: bao
      image: openbao/openbao:2.2.0
      command: ["/bin/sh","-c"]
      args:
        - |
          printf 'disable_mlock = true\nstorage "raft" {\n path = "/bao"\n node_id = "restore-0"\n}\nlistener "tcp" {\n address = "127.0.0.1:8200"\n tls_disable = "true"\n}\napi_addr = "http://127.0.0.1:8200"\ncluster_addr = "http://127.0.0.1:8201"\n' > /tmp/c.hcl
          exec bao server -config=/tmp/c.hcl
      env: [ { name: BAO_ADDR, value: "http://127.0.0.1:8200" } ]
      volumeMounts: [ { name: b, mountPath: /b }, { name: bao, mountPath: /bao } ]
YAML
kubectl -n $NS wait --for=condition=Ready pod/restore --timeout=300s >/dev/null
kubectl -n $NS logs restore -c fetch
echo "== postgres"
for i in $(seq 1 30); do kubectl -n $NS exec restore -c pg -- pg_isready -U postgres -d restore >/dev/null 2>&1 && break; sleep 2; done
# the table's FK points at documents, which a table-only dump doesn't carry: in a
# real restore the rows go back into the app database, where documents exists.
kubectl -n $NS exec restore -c pg -- sh -c 'pg_restore -l /b/keys.dump | grep -v "FK CONSTRAINT" > /tmp/list && pg_restore -U postgres -d restore --no-owner -L /tmp/list /b/keys.dump && echo "restored (FK to documents left out in the throwaway)"'
echo "rows restored: $(kubectl -n $NS exec restore -c pg -- psql -U postgres -d restore -tAc 'select count(*) from document_keys')  (dump says $(kubectl -n $NS exec restore -c pg -- cat /b/keys.rows), production now $(kubectl -n cnpg-database exec homelab-pg-1 -c postgres -- psql -d app -tAc 'select count(*) from document_keys'))"
echo "columns restored: $(kubectl -n $NS exec restore -c pg -- psql -U postgres -d restore -tAc "select string_agg(column_name,',' order by ordinal_position) from information_schema.columns where table_name='document_keys'")"
echo "columns production: $(kubectl -n cnpg-database exec homelab-pg-1 -c postgres -- psql -d app -tAc "select string_agg(column_name,',' order by ordinal_position) from information_schema.columns where table_name='document_keys'")"
echo "== openbao"
# a test value wrapped by production's KEK now, to unwrap from the restored snapshot
PT=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
WT=$(kubectl -n wordsworth get secret wordsworth-openbao -o jsonpath='{.data.WORDSWORTH_OPENBAO_TOKEN}' | base64 -d)
CT=$(kubectl -n openbao exec openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN="$WT" bao write -field=ciphertext transit/encrypt/wordsworth plaintext="$PT")
echo "test value wrapped by production KEK: ${CT%%:*}:${CT#*:}" | cut -c1-24
B="kubectl -n $NS exec -i restore -c bao --"
$B sh -c 'bao operator init -key-shares=1 -key-threshold=1 -format=json > /tmp/init.json && echo initialised-fresh'
$B sh -c 'K=$(sed -n "s/.*\"unseal_keys_b64\":\[\"\([^\"]*\)\".*/\1/p" /tmp/init.json | head -1); [ -n "$K" ] || K=$(tr -d "\n " < /tmp/init.json | sed -n "s/.*\"unseal_keys_b64\":\[\"\([^\"]*\)\".*/\1/p"); bao operator unseal "$K" >/dev/null && echo unsealed-fresh'
$B sh -c 'T=$(tr -d "\n " < /tmp/init.json | sed -n "s/.*\"root_token\":\"\([^\"]*\)\".*/\1/p"); for i in 1 2 3 4 5 6 7 8 9 10; do BAO_TOKEN=$T bao operator raft snapshot restore -force /b/bao.snap 2>/tmp/err && { echo snapshot-restored; break; }; sleep 3; done; [ -s /tmp/err ] && tail -1 /tmp/err || true'
sleep 3
echo "sealed after restore: $($B bao status -format=json 2>/dev/null | tr -d '\n ' | sed -n 's/.*"sealed":\([a-z]*\).*/\1/p')"
kubectl -n openbao get secret openbao-keys -o jsonpath='{.data.unseal_key}' | base64 -d | $B sh -c 'read K; bao operator unseal "$K" >/dev/null && echo unsealed-with-production-key'
sleep 2
RT=$(kubectl -n openbao get secret openbao-keys -o jsonpath='{.data.root_token}' | base64 -d)
printf '%s\n' "$RT" | $B sh -c 'read T; BAO_TOKEN=$T bao read -format=json transit/keys/wordsworth | tr -d "\n " | sed -n "s/.*\"latest_version\":\([0-9]*\).*\"name\":\"\([^\"]*\)\".*/KEK in snapshot: name=\2 latest_version=\1/p"'
echo "KEK in production: $(printf '%s\n' "$RT" | kubectl -n openbao exec -i openbao-0 -- sh -c 'read T; BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=$T bao read -field=latest_version transit/keys/wordsworth') (latest_version)"
GOT=$(printf '%s\n%s\n' "$RT" "$CT" | $B sh -c 'read T; read C; BAO_TOKEN=$T bao write -field=plaintext transit/decrypt/wordsworth ciphertext="$C"')
[ "$GOT" = "$PT" ] && echo "unwrap from restored snapshot: MATCH" || echo "unwrap from restored snapshot: MISMATCH"
