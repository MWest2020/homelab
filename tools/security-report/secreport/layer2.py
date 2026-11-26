"""Layer 2: active, non-destructive checks on Wordsworth and Keycloak.

Rules (Mark, 2026-11-25): no DoS or load, never delete or modify data, no
brute force beyond a handful of tries, test accounts only. In practice:

- GET/HEAD/OPTIONS only, except the token endpoint (a handful of password
  grants for a username that does not exist, all named `selfscan-*`) and one
  unauthenticated POST to /reveal that the proxy must stop before the app.
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
    users. Five is the 'handful' Mark allows."""
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


def ww_reveal_unauth(c) -> Check:
    ch = Check("ww-reveal-without-grant", "wordsworth", "Reveal zonder sessie of grant onmogelijk", repo="wordsworth")
    time.sleep(0.4)
    r = c.post(f"{WW}/documents/00000000-0000-0000-0000-000000000001/reveal", json={"grant_id": "selfscan-none"})
    ch.private = [f"POST /documents/<dummy>/reveal (geen sessie) → {r.status_code}"]
    ch.result = "held" if _is_login_redirect(r) else "broken"
    ch.summary = ("Zonder sessie stopt de proxy het verzoek. Met sessie niet getest: de enige gebruiker in het "
                  "realm is Mark zelf, en die is grant-issuer (zie vraag over een testaccount)."
                  if ch.result == "held" else f"Reveal bereikbaar zonder sessie ({r.status_code}).")
    return ch


def ww_idor() -> Check:
    return Check("ww-idor-documents", "wordsworth", "IDOR op documenten (ander account)", repo="wordsworth",
                 result="skipped",
                 summary="Niet te testen: er is geen tweede, niet-geprivilegieerd account in realm westerweel. "
                         "Zie de vraag over een testgebruiker.")


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
        steps = [
            lambda: kc_admin_direct(c),
            lambda: kc_bruteforce(cfg), lambda: kc_edge_rate_limit(c), lambda: kc_registration(cfg),
            lambda: kc_redirects(c),
            lambda: ww_unauth(c), lambda: ww_path_tricks(c), lambda: ww_header_spoof(c),
            lambda: ww_reveal_unauth(c), ww_idor, lambda: ww_open_redirect(c), lambda: ww_cors(c), ww_direct_api,
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
    return [ch.as_dict() for ch in checks]
