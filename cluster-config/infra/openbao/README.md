# OpenBao bootstrap (operator-only)

OpenBao is deployed **sealed + uninitialised** by design. Initialising it produces
the crown-jewel material (unseal keys + root token). Run these yourself so that
material lands **only in your terminal** — never in git, the cluster, or Claude's
context. Claude receives only the final *scoped* transit token (which can do
nothing but wrap/unwrap the Wordsworth data-key KEK).

In Claude Code you can run each line with the `!` prefix so it executes in this
session's shell; the sensitive output stays with you.

## 1. Initialise + unseal (crown jewels — keep these safe, offline)

```sh
alias bao='kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 bao'

# One unseal key for a single-operator lab (raise shares/threshold for split custody):
bao operator init -key-shares=1 -key-threshold=1
#   -> prints: Unseal Key 1: <UNSEAL_KEY>   and   Initial Root Token: <ROOT_TOKEN>
#   STORE BOTH OFFLINE. After any pod restart, unseal again with the unseal key.

bao operator unseal <UNSEAL_KEY>
bao status        # Sealed: false, Initialized: true
```

## 2. Enable Transit + create the Wordsworth KEK (uses the root token)

```sh
alias baor='kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=<ROOT_TOKEN> bao'

baor secrets enable transit
baor write -f transit/keys/wordsworth            # the KEK; never leaves OpenBao

# A policy limited to wrap/unwrap under that KEK only (no root powers):
printf 'path "transit/encrypt/wordsworth" { capabilities = ["update"] }\npath "transit/decrypt/wordsworth" { capabilities = ["update"] }\n' \
  | baor policy write wordsworth-transit -

# A token bound to that policy — THIS is the only secret Claude needs:
baor token create -policy=wordsworth-transit -period=768h -field=token
#   -> prints <WORDSWORTH_TRANSIT_TOKEN>
```

## 3. Give Wordsworth the scoped token (safe to store as a k8s secret)

```sh
kubectl -n wordsworth create secret generic wordsworth-openbao \
  --from-literal=WORDSWORTH_OPENBAO_TOKEN='<WORDSWORTH_TRANSIT_TOKEN>'
```

Then Claude flips reversible mode on (config + secretRef already prepared): sets
`WORDSWORTH_REVERSIBLE=true` and `WORDSWORTH_OPENBAO_URL`, references the
`wordsworth-openbao` secret, redeploys, and smoke-tests ingest → reveal.

## Notes

- **Restart re-seals.** After an OpenBao pod restart, repeat step 1's `unseal`.
  Auto-unseal (Transit from a second instance, or an HSM) is the production
  hardening noted in ADR-0002; it can be added on request.
- The scoped token has a 768h TTL/period — renew or reissue before expiry.
- Nothing here writes unseal/root material to git or the cluster.
