# convergence

The game's site, 2D demo and game server (MWest2020/convergence), devnet only.
Images and their build: `docs/how-to/deploy.md` in that repository. A new
build goes live by updating both digests in `deployment.yaml`.

- Public: https://convergence.tail8f7877.ts.net (Tailscale Funnel).
- Out-of-band: the `ghcr-pull` image pull secret (the packages are private),
  copied from the `agents` namespace:

  ```
  kubectl get secret ghcr-pull -n agents -o json \
    | jq 'del(.metadata.namespace,.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp,.metadata.annotations,.metadata.ownerReferences)' \
    | kubectl apply -n convergence -f -
  ```
