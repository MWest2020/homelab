# convergence

The game's site, 2D demo and game server (MWest2020/convergence), devnet only.
Images and their build: `docs/how-to/deploy.md` in that repository. A new
build goes live by updating both digests in `deployment.yaml`.

- Public: https://convergence.tail8f7877.ts.net (Tailscale Funnel).
- Out-of-band: the `ghcr-pull` image pull secret (the packages are private),
  copied from the `agents` namespace:

  ```
  kubectl get secret ghcr-pull -n agents -o json \
    | python3 -c 'import json,sys; s=json.load(sys.stdin); s["metadata"]={"name":"ghcr-pull"}; print(json.dumps(s))' \
    | kubectl apply -n convergence -f -
  ```

The Argo CD Application itself was applied once by hand (no root app runs;
see the runbooks index), on 2026-10-24.
