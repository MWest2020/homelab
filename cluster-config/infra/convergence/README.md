# convergence

The game's site, 2D demo and game server (MWest2020/convergence), devnet only.
Images and their build: `docs/how-to/deploy.md` in that repository. A new
build goes live by updating both digests in `deployment.yaml`.

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

The Argo CD Application itself was applied once by hand (no root app runs;
see the runbooks index), on 2026-10-24.
