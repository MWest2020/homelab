#!/usr/bin/env bash
# Can the netnl pod reach Bazibo's mail relay? ONE connection attempt, ever.
#
# Bazibo's code mails should leave through mail.bazibo.nl:587 (Yourhosting
# Plesk, 92.63.174.175). Yourhosting's firewall blocked the home IP on
# 26 Nov 2026 after repeated connections, so this script makes exactly one
# TCP connection (IPv4 only, no retry, 10 s timeout) from inside the netnl
# pod, the path the app itself uses, and then refuses to run again for the
# same host for 6 hours. NEVER put it in a loop, a CronJob or a watch.
#
#   scripts/check-bazibo-smtp.sh                     # reachability + STARTTLS + AUTH offered
#   scripts/check-bazibo-smtp.sh --login             # same connection, plus one login as
#                                                    # hallo@bazibo.nl (OpenBao kv/westerweel/bazibo-mail)
#   scripts/check-bazibo-smtp.sh --host smtp.soverin.net   # test the script against another relay
#
# Exit: 0 reachable (and login ok with --login), 1 unreachable, 2 SMTP/TLS
# problem, 3 refused by the 6-hour guard, 4 login refused.
# Nothing secret is printed: no password, no server banner text.
# Runbook: docusaurus/docs/runbooks/bazibo-nl.md, "Switch Bazibo mail to mail.bazibo.nl".
set -euo pipefail

HOST=mail.bazibo.nl
PORT=587
LOGIN=0
FORCE=0
GAP=${BAZIBO_SMTP_CHECK_MIN_GAP:-21600}
while [ $# -gt 0 ]; do
    case "$1" in
        --host) HOST=$2; shift 2 ;;
        --port) PORT=$2; shift 2 ;;
        --login) LOGIN=1; shift ;;
        --force) FORCE=1; shift ;;   # only after a deliberate decision; still one attempt
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 64 ;;
    esac
done
case "$HOST" in *[!A-Za-z0-9.-]*|"") echo "bad host: $HOST" >&2; exit 64 ;; esac
case "$PORT" in *[!0-9]*|"") echo "bad port: $PORT" >&2; exit 64 ;; esac
if [ "$LOGIN" = 1 ] && [ "$HOST" != mail.bazibo.nl ]; then
    echo "--login only for mail.bazibo.nl (the credentials are hallo@bazibo.nl's)" >&2; exit 64
fi

STATE=${XDG_STATE_HOME:-$HOME/.local/state}/check-bazibo-smtp
mkdir -p "$STATE"
STAMP="$STATE/$HOST.last"
if [ -f "$STAMP" ] && [ "$FORCE" != 1 ]; then
    age=$(( $(date +%s) - $(stat -c %Y "$STAMP") ))
    if [ "$age" -lt "$GAP" ]; then
        echo "refused: last attempt to $HOST was $((age / 60)) min ago (guard: $((GAP / 3600)) h)." >&2
        echo "Yourhosting blocks repeated connections; wait, or --force after a deliberate decision." >&2
        exit 3
    fi
fi
touch "$STAMP"   # before the attempt: a crash still counts as an attempt

# Runs inside the netnl pod (python3 is in the image). One socket, IPv4 only.
read -r -d '' PY <<'EOF' || true
import smtplib, socket, ssl, sys
host, port, login = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "1"
try:
    ipv4 = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
except OSError as exc:
    print(f"UNRESOLVED {host} ({type(exc).__name__})"); sys.exit(1)

class OneShot(smtplib.SMTP):
    def _get_socket(self, h, p, timeout):
        return socket.create_connection((ipv4, p), timeout)  # one address, one try

conn = OneShot(timeout=10)
conn._host = host   # the name STARTTLS verifies the certificate against
try:
    code, _ = conn.connect(host, port)
except (OSError, smtplib.SMTPException) as exc:
    print(f"UNREACHABLE {host}:{port} via {ipv4} ({type(exc).__name__})"); sys.exit(1)
print(f"REACHABLE {host}:{port} via {ipv4} (greeting {code})")
rc = 0
try:
    conn.ehlo()
    if not conn.has_extn("starttls"):
        print("NO STARTTLS offered"); conn.quit(); sys.exit(2)
    conn.starttls(context=ssl.create_default_context())
    conn.ehlo()
    print(f"STARTTLS ok (certificate valid for {host})")
    print("AUTH offered:", conn.esmtp_features.get("auth", "(none)").strip())
    if login:
        user = sys.stdin.readline().strip()
        password = sys.stdin.readline().rstrip("\n")
        try:
            conn.login(user, password)
            print(f"LOGIN ok as {user}")
        except smtplib.SMTPAuthenticationError as exc:
            print(f"LOGIN refused for {user} (SMTP {exc.smtp_code})"); rc = 4
    conn.quit()
except (OSError, ValueError, smtplib.SMTPException, ssl.SSLError) as exc:
    print(f"SMTP/TLS problem: {type(exc).__name__}"); sys.exit(2)
sys.exit(rc)
EOF

# The remote side reads the credentials on jumpy and streams them on stdin
# into the pod; they never touch a file, an argument or this terminal.
# shellcheck disable=SC2016  # expanded on jumpy, not here
REMOTE='set -euo pipefail
creds() {
  R=$(kubectl -n openbao get secret openbao-keys -o jsonpath="{.data.root_token}" | base64 -d)
  B="kubectl -n openbao exec -i openbao-0 -- env BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=$R bao"
  $B kv get -field=address kv/westerweel/bazibo-mail; echo
  $B kv get -field=password kv/westerweel/bazibo-mail; echo
}
if [ "$LOGIN" = 1 ]; then creds; else true; fi \
  | kubectl -n netnl exec -i deploy/netnl -- python3 -c "$PY" "$HOST" "$PORT" "$LOGIN"'

rc=0
# shellcheck disable=SC2029  # the values are meant to expand here
ssh jumpy "HOST=$(printf %q "$HOST") PORT=$PORT LOGIN=$LOGIN PY=$(printf %q "$PY") bash -c $(printf %q "$REMOTE")" || rc=$?
# scripts/switch-bazibo-smtp.sh wants a recent successful login before it switches.
if [ "$rc" = 0 ] && [ "$LOGIN" = 1 ]; then touch "$STATE/$HOST.login-ok"; fi
exit "$rc"
