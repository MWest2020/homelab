#!/usr/bin/env bash
# Switch Bazibo's code mails from the interim Soverin path to mail.bazibo.nl.
#
# Interim (since 27 Nov 2026): no NETNL_BAZIBO_SMTP_HOST, so the code mail
# leaves through Soverin as "Bazibo <mark@westerweel.work>" with
# Reply-To hallo@bazibo.nl (ConfigMap). This script writes the whole Bazibo
# relay into the Secret netnl-bridge in ONE merge patch (host, port, mode,
# username, password, From), so startup never sees a half-written relay
# (internetnl-cli refuses that), then restarts the Deployment. The password
# comes from OpenBao (kv/westerweel/bazibo-mail) on jumpy and travels on
# stdin; nothing is printed.
#
#   scripts/switch-bazibo-smtp.sh             # switch (needs a login-ok from check-bazibo-smtp.sh --login, < 24 h)
#   scripts/switch-bazibo-smtp.sh --rollback  # back to the interim Soverin path
#
#   --force skips the login-ok check (only after a deliberate decision).
#
# Runbook: docusaurus/docs/runbooks/bazibo-nl.md, "Bazibo code mail from netnl".
set -euo pipefail

MODE=switch
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --rollback) MODE=rollback ;;
        --force) FORCE=1 ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *) echo "unknown argument: $arg" >&2; exit 64 ;;
    esac
done

OK=${XDG_STATE_HOME:-$HOME/.local/state}/check-bazibo-smtp/mail.bazibo.nl.login-ok
if [ "$MODE" = switch ] && [ "$FORCE" != 1 ]; then
    if [ ! -f "$OK" ] || [ $(( $(date +%s) - $(stat -c %Y "$OK") )) -gt 86400 ]; then
        echo "refused: no successful 'scripts/check-bazibo-smtp.sh --login' in the last 24 h." >&2
        echo "Switching to a relay that refuses the login would leave every code mail undelivered." >&2
        exit 3
    fi
fi

# shellcheck disable=SC2016  # expanded on jumpy
REMOTE='set -euo pipefail
if [ "$MODE" = rollback ]; then
  printf "%s" "{\"data\":{\"NETNL_BAZIBO_SMTP_HOST\":null,\"NETNL_BAZIBO_SMTP_PORT\":null,\"NETNL_BAZIBO_SMTP_MODE\":null,\"NETNL_BAZIBO_SMTP_USERNAME\":null,\"NETNL_BAZIBO_SMTP_PASSWORD\":null,\"NETNL_BAZIBO_SMTP_FROM\":null}}"
else
  R=$(kubectl -n openbao get secret openbao-keys -o jsonpath="{.data.root_token}" | base64 -d)
  kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN="$R" \
    bao kv get -format=json kv/westerweel/bazibo-mail \
  | python3 -c "
import base64, json, sys
d = json.load(sys.stdin)[\"data\"][\"data\"]
e = lambda v: base64.b64encode(v.encode()).decode()
print(json.dumps({\"data\": {
    \"NETNL_BAZIBO_SMTP_HOST\": e(\"mail.bazibo.nl\"),
    \"NETNL_BAZIBO_SMTP_PORT\": e(\"587\"),
    \"NETNL_BAZIBO_SMTP_MODE\": e(\"starttls\"),
    \"NETNL_BAZIBO_SMTP_USERNAME\": e(d[\"address\"]),
    \"NETNL_BAZIBO_SMTP_PASSWORD\": e(d[\"password\"]),
    \"NETNL_BAZIBO_SMTP_FROM\": e(d[\"address\"]),
}}))"
fi | kubectl -n netnl patch secret netnl-bridge --type merge --patch-file /dev/stdin >/dev/null
kubectl -n netnl rollout restart deploy/netnl >/dev/null
kubectl -n netnl rollout status deploy/netnl --timeout=180s'

# shellcheck disable=SC2029
if ! ssh jumpy "MODE=$MODE bash -c $(printf %q "$REMOTE")"; then
    # The Deployment is Recreate: a pod that does not come up means the whole facade is down.
    echo "FAILED ($MODE): netnl may be down. Check: ssh jumpy kubectl -n netnl get pods" >&2
    [ "$MODE" = switch ] && echo "Back to Soverin: $0 --rollback" >&2
    exit 1
fi
echo "done ($MODE). Verify with one hand-issued code (runbook bazibo-nl)."
