"""Layer 2: active, non-destructive checks on Wordsworth and Keycloak.

Rules (Mark, 2026-11-25): no DoS or load, never delete or modify data, no
brute force beyond a handful of tries, test accounts only. In practice:

- GET/HEAD/OPTIONS, except: the token endpoint (seven password grants in
  all, for usernames that do not exist, all named `selfscan-*`); one
  unauthenticated POST to /reveal that the proxy must stop before the app;
  one browser login as the test user (homelab#85, at most one submit per
  form, never retried); and as that user five POSTs chosen so that they
  can't write even if the gate they test were missing (see ww_reveal and
  ww_ingest_gate).
- Keycloak config is READ via kcadm inside the pod; nothing is written.
- Results: `held` (the control stopped us), `broken` (we got through: a
  finding), `exposed` (reachable, by design or not; context in the note),
  `skipped` (with the reason). `private` holds the exact requests: it goes
  into the private report, never into a public issue.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .util import client, jumpy

IAM = "https://iam.westerweel.work"
WW = "https://wordsworth.westerweel.work"
EVIL = "https://selfscan-redirect-check.invalid/"



@dataclass
class Check:
    id: str
    site: str
    title: str
    result: str = "skipped"
    summary: str = ""
    private: list[str] = field(default_factory=list)
    repo: str = "homelab"

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _get(c: httpx.Client, base: str, raw_path: str, **kw) -> httpx.Response:
    url = httpx.URL(base).copy_with(raw_path=raw_path.encode())
    time.sleep(0.4)  # gentle: a few requests per second at most
    return c.get(url, **kw)


# --------------------------------------------------------------------------- Keycloak

def kc_admin_direct(c) -> Check:
    ch = Check("kc-admin-direct", "iam", "Keycloak admin console/API niet direct publiek")
    seen = []
    for p in ["/admin/", "/admin/master/console/", "/admin/realms"]:
        r = _get(c, IAM, p)
        seen.append(f"GET {p} → {r.status_code}")
    ch.private = seen
    ch.result = "held" if all(s.endswith("404") for s in seen) else "broken"
    ch.summary = "Directe /admin-paden geven 404 van de tunnel." if ch.result == "held" else "Een /admin-pad is direct bereikbaar."
    return ch


ADMIN_API_401 = "HTTP 401 Unauthorized"   # Keycloak's admin REST API without a token


def _public_ok(c, ch: Check) -> bool:
    """Positive control: the public realm answers. Without it, "everything is
    404" would also be what a broken proxy looks like."""
    r = _get(c, IAM, "/realms/westerweel/.well-known/openid-configuration")
    ch.private.append(f"control: GET /realms/westerweel/.well-known/openid-configuration → {r.status_code}")
    if r.status_code != 200:
        ch.summary = f"Niet getest: de publieke realm zelf antwoordt {r.status_code} (proxy of Keycloak stuk?)."
        return False
    return True


def _encoded_traversals() -> list[str]:
    """Every allowed public prefix, climbed back to the admin API with the
    spellings of `..` and `/` that a path filter and Keycloak may read
    differently: plain, percent-encoded (any case), double-encoded, overlong
    UTF-8, %u, a matrix parameter, an encoded slash."""
    segs = ["..", "%2e%2e", ".%2e", "%2e.", "%2E%2E", "..;", "%252e%252e", "%c0%ae%c0%ae", "%u002e%u002e"]
    joins = ["/", "%2f"]
    out = []
    for prefix in ("/realms", "/realms/westerweel", "/resources", "/js"):
        depth = prefix.count("/")
        for seg in segs:
            for j in joins:
                out.append(prefix + "/" + (seg + j) * depth + "admin/realms")
    return out


def kc_path_filter(c, cfg=None) -> Check:
    """Regression for homelab#84 (fixed 2026-11-26 by the keycloak-edge proxy):
    no encoded path reaches the admin API or the admin console; the proxy
    answers 404 to all of them."""
    ch = Check("kc-tunnel-path-filter", "iam",
               "Publiek alleen OIDC van realm westerweel: geen gecodeerd pad bereikt /admin")
    if not _public_ok(c, ch):
        return ch
    reached, not404 = [], []
    paths = _encoded_traversals()
    for p in paths:
        r = _get(c, IAM, p)
        hit = r.status_code == 401 and ADMIN_API_401 in r.text
        ch.private.append(f"GET {p} → {r.status_code}{'  ADMIN API REACHED' if hit else ''}")
        edge_400 = r.status_code == 400 and r.headers.get("server", "").lower() == "cloudflare"
        if hit:
            reached.append(p)
        elif r.status_code != 404 and not edge_400:   # malformed escapes die at Cloudflare's edge
            not404.append(f"{p}={r.status_code}")
    for p in ("/realms/%2e%2e/admin/master/console/", "/admin/master/console/"):
        r = _get(c, IAM, p)
        ch.private.append(f"GET {p} → {r.status_code}")
        if "Keycloak Administration Console" in r.text:
            reached.append(p)
    if reached:
        ch.result = "broken"
        ch.summary = f"{len(reached)} gecodeerde paden bereiken de admin-API of beheerconsole van Keycloak."
    elif not404:
        ch.result = "exposed"
        ch.summary = f"Admin niet bereikt, maar niet alles krijgt 404 van de proxy: {not404[:5]}"
    else:
        ch.result = "held"
        ch.summary = (f"Alle {len(paths) + 2} traversal-varianten worden geweigerd: 404 van de keycloak-edge-proxy, "
                      "of 400 van Cloudflare voor ongeldige escapes.")
    return ch


def kc_master_public(c, cfg: dict | None = None) -> Check:
    """Regression for homelab#84: the master realm (administrators) is not
    public. One password grant for a nonexistent user, like before."""
    ch = Check("kc-master-realm-public", "iam", "Master-realm (beheerders) niet publiek bereikbaar")
    if not _public_ok(c, ch):
        return ch
    wk = _get(c, IAM, "/realms/master/.well-known/openid-configuration")
    time.sleep(0.4)
    tok = c.post(f"{IAM}/realms/master/protocol/openid-connect/token",
                 data={"grant_type": "password", "client_id": "admin-cli",
                       "username": "selfscan-nonexistent-user", "password": "selfscan-wrong"})
    ch.private += [f"GET /realms/master/.well-known/openid-configuration → {wk.status_code}",
                   f"POST /realms/master/protocol/openid-connect/token (nonexistent user) → {tok.status_code}"]
    if cfg:
        m = next((r for r in cfg["realms"] if r["realm"] == "master"), {})
        ch.private.append(f"kcadm: master bruteForceProtected={m.get('bruteForceProtected')}")
    if wk.status_code == 404 and tok.status_code == 404:
        ch.result = "held"
        ch.summary = "Master-realm geeft publiek 404 (discovery en token-endpoint); alleen via de tailnet."
    else:
        ch.result = "broken"
        ch.summary = f"Master-realm publiek bereikbaar (discovery {wk.status_code}, token {tok.status_code})."
    return ch


def kc_xff(c, cfg=None) -> Check:
    """The IP in Keycloak's events is the one Cloudflare saw, not one the
    client chose: keycloak-edge sets X-Forwarded-For from Cf-Connecting-Ip."""
    ch = Check("kc-xff-trust", "iam", "IP-adres in Keycloak-events is niet door de client te kiezen")
    marker = f"selfscan-xff-{int(time.time())}"
    c.post(f"{IAM}/realms/westerweel/protocol/openid-connect/token",
           headers={"X-Forwarded-For": "203.0.113.77"},
           data={"grant_type": "password", "client_id": "admin-cli", "username": marker, "password": "x"})
    time.sleep(3)
    r = jumpy(f"kubectl -n keycloak logs deploy/keycloak --since=10m | grep -o 'ipAddress=\"[^\"]*\".*username=\"{marker}\"' | head -1")
    m = re.search(r'ipAddress="([^"]*)"', r.stdout)
    ip = m.group(1) if m else None
    ch.private = [f"POST token with a spoofed X-Forwarded-For → event ipAddress={ip}"]
    if ip == "203.0.113.77":
        ch.result = "exposed"
        ch.summary = "Keycloak neemt een door de client gezet X-Forwarded-For over: IP's in events zijn onbetrouwbaar."
    elif ip:
        ch.result = "held"
        ch.summary = "Het event noemt het adres dat Cloudflare zag, niet het vervalste."
    else:
        ch.summary = "Event niet teruggevonden in de log."
    return ch


def _kcadm(script: str) -> str:
    """Run read-only kcadm commands in the Keycloak pod. Credentials come from
    the pod's own env; the config file is removed afterwards."""
    wrapped = ('K=/opt/keycloak/bin/kcadm.sh; C="--config /tmp/secreport-kcadm.cfg"; '
               '$K config credentials $C --server http://localhost:8080 --realm master '
               '--user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null 2>&1 || exit 3; '
               + script + '; rm -f /tmp/secreport-kcadm.cfg')
    quoted = wrapped.replace("'", "'\"'\"'")
    r = jumpy(f"kubectl -n keycloak exec -i deploy/keycloak -- bash -c '{quoted}' </dev/null", timeout=180)
    if r.returncode:
        raise RuntimeError(f"kcadm failed ({r.returncode}): {r.stderr[-300:]}")
    return r.stdout


def kc_realm_config() -> dict:
    import json
    out = _kcadm("$K get realms $C --fields realm,bruteForceProtected,failureFactor,permanentLockout,"
                 "registrationAllowed,resetPasswordAllowed,eventsEnabled,passwordPolicy; echo '@@'; "
                 "$K get clients -r master $C --fields clientId,directAccessGrantsEnabled,publicClient,enabled; echo '@@'; "
                 "$K get components -r westerweel $C -q type=org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy "
                 "--fields name,subType,config")
    realms, master_clients, regpol = out.split("@@")
    return {"realms": json.loads(realms), "master_clients": json.loads(master_clients),
            "registration_policies": json.loads(regpol)}


def kc_bruteforce(cfg: dict | None) -> Check:
    ch = Check("kc-login-rate-limit", "iam", "Inlogpogingen worden afgeremd (brute-force-detectie)")
    if not cfg:
        ch.summary = "Keycloak-config niet leesbaar (kcadm)."
        return ch
    for r in cfg["realms"]:
        ch.private.append(f"{r['realm']}: bruteForceProtected={r.get('bruteForceProtected')} "
                          f"failureFactor={r.get('failureFactor')} permanentLockout={r.get('permanentLockout')} "
                          f"registrationAllowed={r.get('registrationAllowed')} eventsEnabled={r.get('eventsEnabled')}")
    ww = next((r for r in cfg["realms"] if r["realm"] == "westerweel"), {})
    ch.result = "held" if ww.get("bruteForceProtected") else "broken"
    ch.summary = (f"Realm westerweel: brute-force-detectie aan, vergrendeling na {ww.get('failureFactor')} fouten "
                  "(per gebruiker, niet per IP)." if ch.result == "held"
                  else "Realm westerweel heeft geen brute-force-detectie.")
    return ch


def kc_edge_rate_limit(c) -> Check:
    """Five wrong password grants for a user that does not exist, 1/s. Shows
    whether anything at the edge throttles; Keycloak itself only locks real
    users. Five of the run's seven nonexistent-user grants (the 'handful')."""
    ch = Check("kc-edge-rate-limit", "iam", "Rate-limit op het token-endpoint aan de rand (Cloudflare)")
    codes = []
    for i in range(5):
        r = c.post(f"{IAM}/realms/westerweel/protocol/openid-connect/token",
                   data={"grant_type": "password", "client_id": "admin-cli",
                         "username": "selfscan-ratelimit-probe", "password": f"selfscan-wrong-{i}"})
        codes.append(r.status_code)
        time.sleep(1)
    ch.private = [f"5× POST token (westerweel, admin-cli, nonexistent user) → {codes}"]
    ch.result = "exposed" if 429 not in codes else "held"
    ch.summary = ("Geen 429 na 5 pogingen: aan de rand wordt niet afgeremd; de bescherming is alleen "
                  "Keycloaks vergrendeling per gebruiker." if ch.result == "exposed" else "Cloudflare remt af (429).")
    return ch


def kc_registration(cfg: dict | None) -> Check:
    ch = Check("kc-anonymous-client-registration", "iam", "Geen anonieme client-registratie")
    if not cfg:
        return ch
    anon = [p for p in cfg["registration_policies"] if p.get("subType") == "anonymous"]
    trusted = next((p for p in anon if p.get("name") == "Trusted Hosts"), None)
    if trusted:
        hosts = trusted.get("config", {}).get("trusted-hosts", [])
        must = trusted.get("config", {}).get("host-sending-registration-request-must-match", ["true"])
        ch.private = [f"Trusted Hosts policy: trusted-hosts={hosts} must-match={must}"]
        ch.result = "held" if not hosts and must == ["true"] else "exposed"
        ch.summary = ("Anonieme registratie geweigerd (Trusted Hosts leeg)." if ch.result == "held"
                      else f"Anonieme registratie toegestaan vanaf {hosts}.")
    else:
        ch.result = "exposed"
        ch.summary = "Geen Trusted-Hosts-policy voor anonieme registratie gevonden: controleren."
    return ch


def kc_redirects(c) -> Check:
    ch = Check("kc-open-redirect", "iam", "Geen open redirect in de OAuth-flow van Keycloak")
    bad = []
    variants = [EVIL, "https://wordsworth.westerweel.work.selfscan.invalid/oauth2/callback",
                "https://wordsworth.westerweel.work@selfscan.invalid/oauth2/callback",
                "https://wordsworth.westerweel.work/oauth2/callback/../../x", "//selfscan.invalid/"]
    for client_id in ("wordsworth", "wanderer"):
        for v in variants:
            q = urllib.parse.urlencode({"client_id": client_id, "redirect_uri": v,
                                        "response_type": "code", "scope": "openid"})
            r = _get(c, IAM, f"/realms/westerweel/protocol/openid-connect/auth?{q}")
            loc = r.headers.get("location", "")
            ok = r.status_code == 400 or ("Invalid parameter" in r.text)
            ch.private.append(f"auth {client_id} redirect_uri={v} → {r.status_code} {loc[:60]}")
            if not ok:
                bad.append((client_id, v, r.status_code))
    q = urllib.parse.urlencode({"client_id": "wordsworth", "post_logout_redirect_uri": EVIL})
    r = _get(c, IAM, f"/realms/westerweel/protocol/openid-connect/logout?{q}")
    ch.private.append(f"logout post_logout_redirect_uri=evil → {r.status_code} {r.headers.get('location', '')[:60]}")
    if r.status_code in (301, 302, 303) and _offsite(r.headers.get("location", ""), IAM + "/"):
        bad.append(("logout", EVIL, r.status_code))
    ch.result = "broken" if bad else "held"
    ch.summary = "Alle afwijkende redirect_uri's geweigerd." if not bad else f"Geaccepteerd: {bad}"
    return ch


# --------------------------------------------------------------------------- Wordsworth

WW_GET_ROUTES = ["/", "/ask", "/combinations", "/documents", "/documents/00000000-0000-0000-0000-000000000001",
                 "/documents/00000000-0000-0000-0000-000000000001/anonymized",
                 "/documents/00000000-0000-0000-0000-000000000001/redacted.pdf",
                 "/documents/00000000-0000-0000-0000-000000000001/state", "/dossier",
                 "/export/anonymized.zip", "/export/ranking.csv", "/feedback", "/grants/x", "/group-roles",
                 "/hybrid", "/login", "/metrics", "/roles", "/search", "/topics", "/docs", "/openapi.json",
                 "/redoc", "/console", "/console/login"]


def _offsite(location: str, base: str = WW + "/") -> bool:
    """Would a browser following this Location leave our host? Browsers drop
    raw tab/CR/LF and read a backslash as a slash (WHATWG URL); percent-encoded
    ones stay literal path characters, so `/%2F%2Fevil` is not off-site."""
    if not location:
        return False
    s = location.replace("\t", "").replace("\r", "").replace("\n", "").replace("\\", "/")
    host = urllib.parse.urlparse(urllib.parse.urljoin(base, s)).hostname
    return host is not None and host != urllib.parse.urlparse(base).hostname


def _is_login_redirect(r: httpx.Response) -> bool:
    loc = r.headers.get("location", "")
    return (r.status_code in (302, 303, 307) and (loc.startswith(IAM) or loc.startswith("/oauth2/"))) \
        or r.status_code in (401, 403)


def ww_unauth(c) -> Check:
    ch = Check("ww-unauthenticated-routes", "wordsworth", "Geen API-route zonder login bereikbaar", repo="wordsworth")
    leaks = []
    for p in WW_GET_ROUTES:
        r = _get(c, WW, p)
        ch.private.append(f"GET {p} → {r.status_code}")
        if not _is_login_redirect(r):
            leaks.append(f"{p}={r.status_code}")
    h = _get(c, WW, "/health")
    ch.private.append(f"GET /health → {h.status_code} (bewust open)")
    ch.result = "broken" if leaks else "held"
    ch.summary = (f"Alle {len(WW_GET_ROUTES)} routes sturen zonder sessie naar Keycloak; alleen /health is open."
                  if not leaks else f"Zonder login bereikbaar: {leaks}")
    return ch


def ww_path_tricks(c) -> Check:
    ch = Check("ww-proxy-path-bypass", "wordsworth",
               "skip-auth-route ^/health$ niet te misbruiken met padtrucs", repo="homelab")
    leaks = []
    for p in ["/health/../documents", "/health/%2e%2e/documents", "/health%2f..%2fdocuments",
              "/health;/../documents", "//documents", "/health/", "/%68ealth/../documents",
              "/health?/../documents", "/HEALTH", "/oauth2/../documents", "/ping/../documents"]:
        r = _get(c, WW, p)
        body = r.text[:200]
        ch.private.append(f"GET {p} → {r.status_code} {body[:50]!r}")
        if r.status_code == 200 and '"status"' not in body and "OK" != body.strip():
            leaks.append(p)
    ch.result = "broken" if leaks else "held"
    ch.summary = "Geen padtruc komt zonder login bij de app." if not leaks else f"Lek via {leaks}"
    return ch


def ww_header_spoof(c) -> Check:
    ch = Check("ww-proxy-header-spoof", "wordsworth", "Vervalste identiteitskoppen worden genegeerd", repo="homelab")
    fake_jwt = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJlbWFpbCI6Im1hcmtAd2VzdGVyd2VlbC53b3JrIn0."
    headers_list = [
        {"X-Forwarded-User": "mark", "X-Forwarded-Email": "mark@westerweel.work"},
        {"X-Auth-Request-User": "mark", "X-Auth-Request-Email": "mark@westerweel.work"},
        {"Authorization": f"Bearer {fake_jwt}"},
        {"Cf-Access-Jwt-Assertion": fake_jwt},
        {"X-Api-Key": "selfscan-not-a-key"},
        {"X-Original-URL": "/health", "X-Rewrite-URL": "/health"},
    ]
    leaks = []
    for h in headers_list:
        r = _get(c, WW, "/documents", headers=h)
        ch.private.append(f"GET /documents + {list(h)} → {r.status_code}")
        if not _is_login_redirect(r):
            leaks.append(list(h))
    ch.result = "broken" if leaks else "held"
    ch.summary = "oauth2-proxy negeert alle vervalste koppen." if not leaks else f"Doorgelaten met {leaks}"
    return ch


# --------------------------------------------------------------------------- test user (homelab#85)
#
# Mark, 2026-11-26: "Maak een test gebruiker aan." One realm user in
# westerweel, `selfscan`, with no app roles, no groups, and an address that is
# not on either Wordsworth label list (a clearly fake `.invalid` one). Its
# password and TOTP secret live in SELFSCAN_ENV (0600, not in git). The checks
# below log in as that user through oauth2-proxy exactly like a browser does,
# then only READ, plus refused POSTs that can't write anything even if the
# gate were missing (see each check).

SELFSCAN_ENV = Path.home() / ".config/security-report/selfscan.env"
_last_totp_step = 0


def _totp(secret: str, step: int) -> str:
    """RFC 6238, as realm westerweel is configured (HmacSHA1, 6 digits, 30 s).
    Keycloak's HMAC key is the secret string's bytes (its QR code is Base32 of
    those bytes)."""
    import hashlib
    import hmac
    import struct
    d = hmac.new(secret.encode(), struct.pack(">Q", step), hashlib.sha1).digest()
    o = d[-1] & 0x0F
    return f"{(struct.unpack('>I', d[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def _fresh_totp(secret: str) -> str:
    """Codes are single-use in this realm: never send the same step twice."""
    global _last_totp_step
    step = int(time.time() // 30)
    if step <= _last_totp_step:
        time.sleep(30 - time.time() % 30 + 1)
        step = int(time.time() // 30)
    _last_totp_step = step
    return _totp(secret, step)


def _form(html_text: str) -> tuple[str, dict[str, str]]:
    """The first form's action and its hidden inputs."""
    import html as h
    m = re.search(r'<form\b[^>]*\baction="([^"]+)"', html_text)
    if not m:
        raise RuntimeError("no form on the Keycloak page")
    hidden = {}
    for tag in re.findall(r"<input\b[^>]*>", html_text):
        if 'type="hidden"' in tag:
            n = re.search(r'\bname="([^"]+)"', tag)
            v = re.search(r'\bvalue="([^"]*)"', tag)
            if n:
                hidden[n.group(1)] = h.unescape(v.group(1)) if v else ""
    return h.unescape(m.group(1)), hidden


def _check_env_file() -> None:
    """Same rule as the private checks: ours, and no group/other bits."""
    import os
    st = SELFSCAN_ENV.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise PermissionError(f"{SELFSCAN_ENV} must be owned by this user with mode 0600 "
                              f"(is {oct(st.st_mode & 0o777)}); not using it")


def _save_env(key: str, value: str) -> None:
    """Add or replace one line, atomically: temp file (0600) in the same
    directory, fsync, rename. A crash never leaves a half-written file."""
    import os
    import tempfile
    _check_env_file()
    lines = [ln for ln in SELFSCAN_ENV.read_text().splitlines() if not ln.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    fd, tmp = tempfile.mkstemp(dir=SELFSCAN_ENV.parent, prefix=".selfscan.", text=True)  # mode 0600
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SELFSCAN_ENV)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def selfscan_session() -> httpx.Client:
    """A client holding an oauth2-proxy session for the test user, or raise.
    Handles the one-time TOTP enrolment (realm policy: 2FA for everyone) and
    stores the secret next to the password."""
    from .util import read_env
    if not SELFSCAN_ENV.exists():
        raise FileNotFoundError(f"{SELFSCAN_ENV} missing")
    _check_env_file()
    env = read_env(SELFSCAN_ENV)
    if not env.get("SELFSCAN_PASSWORD"):
        raise FileNotFoundError(f"{SELFSCAN_ENV} missing or without SELFSCAN_PASSWORD")
    s = client()
    submitted: set[str] = set()   # one submit per form kind, never a retry: a
    #                               wrong password or code must not turn into
    #                               a run of failed logins and a lockout
    r = _get(s, WW, "/oauth2/start?rd=%2F")
    for _ in range(15):
        if r.status_code in (301, 302, 303, 307):
            loc = urllib.parse.urljoin(str(r.url), r.headers["location"])
            host = urllib.parse.urlparse(loc).hostname
            if host not in ("wordsworth.westerweel.work", "iam.westerweel.work"):
                raise RuntimeError(f"login left our hosts: {host}")
            if loc.startswith(WW) and "/oauth2/" not in loc:
                break                       # back at the app: logged in
            time.sleep(0.4)
            r = s.get(loc)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"login: unexpected {r.status_code} at {urllib.parse.urlparse(str(r.url)).path}")
        page = r.text
        if re.search(r'class="[^"]*(input-error|alert-error|pf-m-danger)', page) \
                or 'aria-invalid="true"' in page:
            raise RuntimeError("Keycloak shows an error on its form (wrong password or code?); not retrying")
        kind = ("password" if 'name="password"' in page else "totp-setup" if 'name="totpSecret"' in page
                else "otp" if 'name="otp"' in page else "?")
        if kind in submitted:
            raise RuntimeError(f"Keycloak asks for the {kind} form again; not retrying")
        submitted.add(kind)
        action, data = _form(page)
        if kind == "password":
            data |= {"username": env["SELFSCAN_USER"], "password": env["SELFSCAN_PASSWORD"]}
        elif kind == "totp-setup":
            secret = data["totpSecret"]
            _save_env("SELFSCAN_TOTP_SECRET", secret)
            env["SELFSCAN_TOTP_SECRET"] = secret
            data |= {"totp": _fresh_totp(secret), "userLabel": "selfscan"}
        elif kind == "otp":
            if not env.get("SELFSCAN_TOTP_SECRET"):
                raise RuntimeError("Keycloak asks for a TOTP code but SELFSCAN_TOTP_SECRET is not set")
            data |= {"otp": _fresh_totp(env["SELFSCAN_TOTP_SECRET"])}
        else:
            title = (re.findall(r"<title>([^<]*)</title>", page) or ["?"])[0]
            raise RuntimeError(f"login: unknown Keycloak page {title!r}")
        time.sleep(0.4)
        r = s.post(action, data=data)
    if not any(c.name.startswith("_oauth2_proxy") for c in s.cookies.jar):
        raise RuntimeError("login finished without an oauth2-proxy session cookie")
    return s


def _ww_sample_ids() -> dict:
    """One real document id and one real DEAD grant id (revoked or expired,
    issued to someone else), read-only from Wordsworth's database, so the
    checks below aim at things that exist. Deliberately never a live grant:
    if recipient binding ever regressed, a live one would perform a real,
    audited reveal for the test user."""
    import json
    py = ("import os,json\nfrom sqlalchemy import create_engine,text\n"
          "e=create_engine(os.environ['WORDSWORTH_DATABASE_URL'])\n"
          "with e.connect() as c:\n"
          " c.execute(text('SET TRANSACTION READ ONLY'))\n"
          " d=c.execute(text('select d.id from documents d join document_texts t on t.document_id=d.id "
          "order by d.id limit 1')).scalar()\n"
          " g=c.execute(text(\"select grant_id,document_id from grants where document_id is not null "
          "and (status='revoked' or expires_at < now()) order by created_at desc limit 1\")).first()\n"
          " print(json.dumps({'doc':str(d) if d else None,'grant':g[0] if g else None,"
          "'grant_doc':str(g[1]) if g else None}))\n")
    r = jumpy("kubectl -n wordsworth exec -i deploy/wordsworth-api -- python -", input=py, timeout=60)
    if r.returncode:
        raise RuntimeError(f"sample ids: {r.stderr[-200:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def _session_ok(s: httpx.Client) -> bool:
    """Does Wordsworth itself see an identity-provider caller? /console/login
    sends a recognised one on to /console instead of showing the key form."""
    r = _get(s, WW, "/console/login")
    return r.status_code == 303 and r.headers.get("location", "").endswith("/console")


def _app_403(r: httpx.Response) -> bool:
    """A refusal by Wordsworth itself (its JSON detail), not by something in
    front of it (a WAF 403 would otherwise read as `held`)."""
    if r.status_code != 403:
        return False
    try:
        detail = str(r.json().get("detail", ""))
    except ValueError:
        return False
    return "not authorized" in detail or "not applicable" in detail


def ww_idor(s: httpx.Client | None, ids: dict | None, why: str = "") -> Check:
    """Wordsworth has no per-user ownership; access is the corpus-read label
    list. So the IDOR question is: can a logged-in user who is NOT on that list
    read a real document (or any corpus data) by id? GET only."""
    ch = Check("ww-idor-documents", "wordsworth", "Ingelogde gebruiker zonder leesrecht leest geen documenten",
               repo="wordsworth")
    if s is None or not ids or not ids.get("doc"):
        ch.summary = f"Niet getest: {why or 'geen document-id'}"
        return ch
    if not _session_ok(s):
        ch.summary = "Niet getest: Wordsworth herkent de sessie van de testgebruiker niet."
        return ch
    doc, ghost = ids["doc"], "00000000-0000-0000-0000-000000000001"
    paths = [f"/documents/{doc}", f"/documents/{doc}/anonymized", f"/documents/{doc}/state",
             f"/documents/{doc}/redacted.pdf", f"/documents/{ghost}/anonymized", "/export/anonymized.zip",
             "/export/ranking.csv?q=de", "/search?q=de", "/hybrid?q=de", "/roles", "/group-roles",
             f"/grants/{ids.get('grant') or 'x'}",
             "/console", "/console/documents", f"/console/documents/{doc}", "/console/search?q=de",
             "/console/topics", "/console/feedback", "/console/combinations", "/console/roles"]
    leaks = []
    for p in paths:
        r = _get(s, WW, p)
        shown = p.replace(doc, "<doc>").replace(ids.get("grant") or "\0", "<grant>")
        ch.private.append(f"GET {shown} (testgebruiker) → {r.status_code} {len(r.content)}B")
        if not _app_403(r):
            leaks.append(f"{shown}={r.status_code}")
    real = _get(s, WW, f"/documents/{doc}/anonymized").status_code
    fake = _get(s, WW, f"/documents/{ghost}/anonymized").status_code
    ch.private.append(f"bestaand versus niet-bestaand id → {real} / {fake}")
    # Anything but Wordsworth's own 403 counts: a 200 is a leak, a 404 or a
    # foreign 403 means this run didn't test what it says. Both are reported.
    ch.result = "broken" if any("=200" in x for x in leaks) else ("exposed" if leaks else "held")
    ch.summary = (f"Alle {len(paths)} lees-routes (API en console) weigeren de testgebruiker ({real}); "
                  "een bestaand en een verzonnen document-id krijgen hetzelfde antwoord."
                  if not leaks else f"Niet door Wordsworth zelf geweigerd: {leaks}")
    if not leaks and real != fake:
        ch.result = "exposed"
        ch.summary = f"Geweigerd, maar bestaand ({real}) en verzonnen ({fake}) id verschillen: bestaan is af te leiden."
    return ch


def ww_reveal(c: httpx.Client, s: httpx.Client | None, ids: dict | None, why: str = "") -> Check:
    """Reveal without a grant. 1) No session: oauth2-proxy must stop it.
    2) The test user (not a grant issuer): reveal with an unknown grant id and
    with a real grant id issued to someone else; mint a grant. The mint uses a
    malformed document id, so even a missing gate can't write: 403 = gate,
    400 = the gate is missing."""
    ch = Check("ww-reveal-without-grant", "wordsworth", "Reveal zonder geldige grant onmogelijk", repo="wordsworth")
    time.sleep(0.4)
    r = c.post(f"{WW}/documents/00000000-0000-0000-0000-000000000001/reveal", json={"grant_id": "selfscan-none"})
    ch.private = [f"POST /documents/<dummy>/reveal (geen sessie) → {r.status_code}"]
    bad = [] if _is_login_redirect(r) else [f"zonder sessie {r.status_code}"]
    if s is None or not ids or not ids.get("doc") or not _session_ok(s):
        ch.result = "broken" if bad else "skipped"
        ch.summary = ("Zonder sessie stopt de proxy het verzoek; het deel met sessie liep niet: "
                      f"{why or 'sessie van de testgebruiker niet herkend'}." if not bad else f"Reveal bereikbaar: {bad}")
        return ch
    doc = ids["doc"]
    tries = [("reveal, verzonnen grant", f"/documents/{doc}/reveal", {"grant_id": "selfscan-no-such-grant"}),
             ("reveal.pdf, verzonnen grant", f"/documents/{doc}/reveal.pdf", {"grant_id": "selfscan-no-such-grant"})]
    if ids.get("grant") and ids.get("grant_doc"):
        tries.append(("reveal, verlopen/ingetrokken grant van een ander", f"/documents/{ids['grant_doc']}/reveal",
                      {"grant_id": ids["grant"]}))
    tries.append(("grant uitgeven", "/grants", {"document_id": "selfscan-not-a-uuid", "recipient": "selfscan",
                                                "allowed_types": ["PERSON"]}))
    for label_, path, body in tries:
        time.sleep(0.4)
        r = s.post(f"{WW}{path}", json=body)
        ch.private.append(f"POST {label_} (testgebruiker) → {r.status_code} {r.text[:60]!r}")
        if not _app_403(r):
            bad.append(f"{label_}={r.status_code}")
    ch.result = "broken" if bad else "held"
    ch.summary = ("Zonder sessie stopt de proxy het verzoek. Als ingelogde gebruiker zonder grant-recht: "
                  "reveal met een verzonnen of een verlopen/ingetrokken grant van een ander en zelf een grant "
                  "uitgeven geven allemaal 403 van Wordsworth."
                  if not bad else f"Niet geweigerd: {bad}")
    return ch


def ww_ingest_gate(s: httpx.Client | None, why: str = "") -> Check:
    """wordsworth#526, fixed in #528: POST /ingest requires the corpus-read
    list. As the test user, one POST without a `files` field, so nothing can
    be stored even if the gate were missing: Wordsworth's own 403 = gated,
    422 = validation reached (the gate is missing)."""
    ch = Check("ww-ingest-gate", "wordsworth", "Ingest alleen voor wie op de corpus-leeslijst staat",
               repo="wordsworth")
    if s is None or not _session_ok(s):
        ch.summary = f"Niet getest: {why or 'Wordsworth herkent de sessie van de testgebruiker niet.'}"
        return ch
    time.sleep(0.4)
    r = s.post(f"{WW}/ingest", files={"selfscan-nofiles": ("selfscan.txt", b"", "text/plain")})
    ch.private = [f"POST /ingest zonder files-veld (testgebruiker) → {r.status_code} {r.text[:60]!r}"]
    if _app_403(r):
        ch.result = "held"
        ch.summary = "Ingest weigert een ingelogde gebruiker zonder leesrecht (403 van Wordsworth)."
    elif r.status_code == 422:
        ch.result = "broken"
        ch.summary = "Een ingelogde gebruiker zonder leesrecht komt langs de poort van ingest."
    else:
        ch.result = "exposed"
        ch.summary = f"Niet door Wordsworth zelf geweigerd: {r.status_code}."
    return ch


def ww_open_redirect(c) -> Check:
    ch = Check("ww-proxy-open-redirect", "wordsworth", "Geen open redirect via oauth2-proxy (rd=)", repo="homelab")
    bad = []
    for v in [EVIL, "//selfscan.invalid/", "/\\selfscan.invalid/", "/\\\\selfscan.invalid/", "https:selfscan.invalid",
              "/%2F%2Fselfscan.invalid/", "/%09/selfscan.invalid/", "https://wordsworth.westerweel.work.selfscan.invalid/",
              "https://wordsworth.westerweel.work@selfscan.invalid/"]:
        q = urllib.parse.urlencode({"rd": v})
        r = _get(c, WW, f"/oauth2/start?{q}")
        loc = r.headers.get("location", "")
        state = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get("state", [""])[0]
        rd = state.split(":", 1)[1] if ":" in state else ""
        s = _get(c, WW, f"/oauth2/sign_out?{q}")
        sloc = s.headers.get("location", "")
        ch.private.append(f"start rd={v!r} → state rd={rd!r}; sign_out → {s.status_code} {sloc[:50]!r}")
        if _offsite(rd) or _offsite(sloc):
            bad.append(v)
    ch.result = "broken" if bad else "held"
    ch.summary = ("Geen rd= leidt de browser naar een andere host (externe doelen worden /, gecodeerde "
                  "varianten blijven een pad op wordsworth)." if not bad else f"Doorgelaten: {bad}")
    return ch


def ww_cors(c) -> Check:
    ch = Check("ww-cors", "wordsworth", "CORS spiegelt geen vreemde origin met credentials", repo="wordsworth")
    bad = []
    for origin in ("https://selfscan.invalid", "https://mwest2020.github.io"):
        time.sleep(0.4)
        r = c.options(f"{WW}/documents", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        acao = r.headers.get("access-control-allow-origin")
        acac = r.headers.get("access-control-allow-credentials")
        ch.private.append(f"OPTIONS /documents Origin={origin} → {r.status_code} ACAO={acao} ACAC={acac}")
        if origin.endswith(".invalid") and acao in (origin, "*") and acac == "true":
            bad.append(origin)
    ch.result = "broken" if bad else "held"
    ch.summary = "Geen vreemde origin gespiegeld." if not bad else f"Gespiegeld: {bad}"
    return ch


def ww_direct_api() -> Check:
    """The API itself must only be reachable through oauth2-proxy (public) or
    the tailnet. Checks the live tunnel config and Funnel annotations."""
    ch = Check("ww-direct-api", "wordsworth", "API alleen via oauth2-proxy publiek bereikbaar", repo="homelab")
    r = jumpy("for p in $(kubectl -n wordsworth get pods -l app=wordsworth,component=tunnel -o name); do "
              "kubectl -n wordsworth logs $p | grep 'Updated to new configuration' | tail -1; done; "
              "kubectl get svc,ingress -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name} "
              "{.metadata.annotations.tailscale\\.com/funnel}{\"\\n\"}{end}' | grep wordsworth || true")
    services = set(re.findall(r'\\"service\\":\\"([^\\]+)\\"', r.stdout)) or set(re.findall(r'"service":"([^"]+)"', r.stdout))
    funnel = [line for line in r.stdout.splitlines() if line.startswith("wordsworth/") and line.strip().endswith("true")]
    ch.private = [f"tunnel services: {sorted(services)}", f"funnel on wordsworth: {funnel}"]
    if not services:
        ch.summary = "Tunnelconfig niet gevonden in de cloudflared-logs (pods herstart?)."
        return ch
    direct = [s for s in services if "wordsworth-api" in s]
    ch.result = "broken" if direct or funnel else "held"
    ch.summary = ("De tunnel wijst alleen naar wordsworth-auth:4180; geen Funnel op wordsworth."
                  if ch.result == "held" else f"Directe route naar de API: {direct or funnel}")
    return ch


# --------------------------------------------------------------------------- private checks

PRIVATE_CHECKS = Path.home() / ".config/security-report/private_checks.py"


def load_private():
    """Checks for findings that are still OPEN live outside this public repo,
    in ~/.config/security-report/private_checks.py (0600): their requests are
    a working exploit until the fix lands. Once fixed, a check moves in here
    as a regression test. The module exports CHECKS (callables taking
    (client, keycloak_cfg) and returning a Check), SEVERITY, WHERE and
    questions(l2)."""
    if not PRIVATE_CHECKS.exists():
        return None
    st = PRIVATE_CHECKS.stat()
    import os
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise PermissionError(f"{PRIVATE_CHECKS} must be owned by this user with mode 0600 "
                              f"(is {oct(st.st_mode & 0o777)}); not executing it")
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("secreport_private_checks", PRIVATE_CHECKS)
    mod = importlib.util.module_from_spec(spec)
    # No __pycache__ next to it: compiled private checks must not land in a
    # world-readable directory.
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def run() -> list[dict]:
    checks: list[Check] = []
    with client() as c:
        try:
            cfg = kc_realm_config()
        except Exception as e:  # noqa: BLE001 - report it, keep going
            cfg = None
            checks.append(Check("kc-config-read", "iam", "Keycloak-config lezen", summary=str(e)[:200]))
        s, ids, why = None, None, ""
        try:
            ids = _ww_sample_ids()
            s = selfscan_session()
        except Exception as e:  # noqa: BLE001 - the two checks report it as skipped
            why = f"{type(e).__name__}: {str(e)[:150]}"
        steps = [
            lambda: kc_admin_direct(c),
            lambda: kc_bruteforce(cfg), lambda: kc_edge_rate_limit(c), lambda: kc_registration(cfg),
            lambda: kc_redirects(c),
            lambda: kc_path_filter(c, cfg), lambda: kc_master_public(c, cfg), lambda: kc_xff(c),
            lambda: ww_unauth(c), lambda: ww_path_tricks(c), lambda: ww_header_spoof(c),
            lambda: ww_reveal(c, s, ids, why), lambda: ww_idor(s, ids, why),
            lambda: ww_ingest_gate(s, why),
            lambda: ww_open_redirect(c), lambda: ww_cors(c), ww_direct_api,
        ]
        try:
            priv = load_private()
            if priv is not None:
                steps += [lambda f=f: f(c, cfg) for f in priv.CHECKS]
        except Exception as e:  # noqa: BLE001 - a broken or unsafe private file must not kill the public checks
            checks.append(Check("private-checks", "?", "Private checks laden",
                                summary=f"{type(e).__name__}: {str(e)[:200]}"))
        for step in steps:
            try:
                checks.append(step())
            except Exception as e:  # noqa: BLE001
                checks.append(Check(getattr(step, "__name__", "check"), "?", "check failed",
                                    summary=f"{type(e).__name__}: {str(e)[:200]}"))
        if s is not None:
            s.close()
    return [ch.as_dict() for ch in checks]
