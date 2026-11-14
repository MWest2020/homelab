# convergence

The game's site and the RPG demo at `/play-rpg/` (MWest2020/convergence), devnet
only: two containers, `web` (nginx, the site, the proxy) and `rpg` (the RPG-JS
game server). The first demo's `server` container (`/play/`, `/ws`) was retired
on 2026-11-11; `/play` redirects to `/play-rpg/`. Images and their build:
`docs/how-to/deploy.md` in that repository. A new build goes live by updating
the digests (web, rpg) in `deployment.yaml`. Health: `/healthz` on the public
host is answered by the rpg container through nginx.

- Public: https://convergence.westerweel.work (Cloudflare tunnel `convergence`,
  `tunnel.yaml`). The Funnel name https://convergence.tail8f7877.ts.net is
  configured but has no public DNS until the tailnet ACL grants `tag:k8s` the
  `funnel` node attribute.
- Out-of-band: `convergence-tunnel` (key `TUNNEL_TOKEN`, no trailing newline),
  from the Cloudflare API: `GET accounts/<id>/cfd_tunnel/<tunnel-id>/token`.
- Out-of-band: the `ghcr-pull` image pull secret (the packages are private),
  copied from the `agents` namespace:

  ```
  kubectl get secret ghcr-pull -n agents -o json \
    | python3 -c 'import json,sys; s=json.load(sys.stdin); s["metadata"]={"name":"ghcr-pull"}; print(json.dumps(s))' \
    | kubectl apply -n convergence -f -
  ```

- Out-of-band: `convergence-devnet-authority` (key `authority`, the game's
  Solana **devnet** authority as a JSON array of 64 numbers; public key
  `HV8MjgB8b725dE3urVFxtKQmED6QQdmknDwJqhzgnShB`), read by the rpg container
  as `CV_AUTHORITY_KEY`. Backup in OpenBao `kv/convergence/devnet-authority`
  (fields `authority`, `pubkey`, `cluster`, `shard_mint`). Recreate from jumpy,
  nothing printed:

  ```
  R=$(kubectl -n openbao get secret openbao-keys -o jsonpath='{.data.root_token}' | base64 -d)
  kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=$R \
    bao kv get -field=authority kv/convergence/devnet-authority </dev/null \
    | kubectl -n convergence create secret generic convergence-devnet-authority --from-file=authority=/dev/stdin
  ```

The Argo CD Application itself was applied once by hand (no root app runs;
see the runbooks index), on 2026-10-24.
