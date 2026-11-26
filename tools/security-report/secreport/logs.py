"""Bot traffic from the logs we can read ourselves.

`collect()` runs every few hours: oauth2-proxy's logs rotate away within a day
(kube-probe lines fill the kubelet's 10 MB), and Plesk keeps five days. Lines
go into CACHE/<site>/<UTC day>.log, deduplicated, probes dropped. The Plesk
pull is attempted at most once a day and stops after repeated failures; the
OpenBao token is renewed once a day on its own; old cache files and reports
are pruned.

`summarize()` turns a week of cached lines into per-site numbers.
"""
from __future__ import annotations

import datetime as dt
import ftplib
import gzip
import io
import json
import re
import socket
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import geo
from .config import (BAO_ENV, CACHE, CACHE_DAYS, K8S_LOGS, PLESK_BAO_PATH, PLESK_LOG_PREFIXES, PLESK_MAX_FAILURES,
                     PLESK_MIN_HOURS, PLESK_SITE, REPORT_WEEKS, STATE)
from .util import jumpy, read_env

# ------------------------------------------------------------------ collecting


def _append(site: str, lines_by_day: dict[str, list[str]]) -> int:
    added = 0
    for day, lines in lines_by_day.items():
        f = CACHE / site / f"{day}.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        have = set(f.read_text(encoding="utf-8", errors="replace").splitlines()) if f.exists() else set()
        new = [ln for ln in dict.fromkeys(lines) if ln and ln not in have]
        if new:
            with f.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write("\n".join(new) + "\n")
            added += len(new)
    return added


def _bucket(src, text: str) -> dict[str, list[str]]:
    by_day: dict[str, list[str]] = defaultdict(list)
    for ln in text.splitlines():
        if any(d in ln for d in src.drop):
            continue
        if src.fmt == "keycloak" and "org.keycloak.events" not in ln:
            continue
        m = re.match(r"\[[^\]]+\] (\d{4}-\d\d-\d\d)T", ln)
        if m:
            by_day[m.group(1)].append(ln)
    return by_day


def collect_k8s() -> dict[str, int | str]:
    """Each source on its own: one failing namespace must not cost the rest."""
    out: dict[str, int | str] = {}
    for src in K8S_LOGS:
        try:
            r = jumpy(f"kubectl -n {src.namespace} logs -l {src.selector} -c {src.container} --since=26h "
                      f"--timestamps --prefix --max-log-requests=6 --tail=-1", timeout=300)
            if r.returncode and not r.stdout:
                out[src.site] = f"error: {r.stderr.strip()[-160:]}"
                continue
            out[src.site] = _append(src.site, _bucket(src, r.stdout))
        except Exception as e:  # noqa: BLE001
            out[src.site] = f"error: {type(e).__name__}: {e}"[:200]
    return out


# ---- OpenBao token (periodic, 768h): renewed once a day, independent of Plesk

def _bao(cmd: str, tok: str):
    return jumpy("kubectl -n openbao exec -i openbao-0 -- sh -c 'read -r T; BAO_ADDR=http://127.0.0.1:8200 "
                 f"BAO_TOKEN=$T {cmd}'", input=tok + "\n")


def renew_bao_token() -> str:
    tok = read_env(BAO_ENV).get("BAO_TOKEN")
    if not tok:
        return f"error: {BAO_ENV} missing"
    stamp = STATE / "bao-renewed"
    if stamp.exists() and time.time() - stamp.stat().st_mtime < 20 * 3600:
        return "skipped: renewed < 20 h ago"
    r = _bao("bao token renew >/dev/null", tok)
    if r.returncode:
        return f"error: {r.stderr.strip()[-160:]}"
    stamp.touch()
    return "renewed"


def _plesk_creds() -> dict:
    tok = read_env(BAO_ENV).get("BAO_TOKEN")
    if not tok:
        raise RuntimeError(f"{BAO_ENV} missing (BAO_TOKEN with policy security-report)")
    r = _bao(f"bao kv get -format=json {PLESK_BAO_PATH}", tok)
    if r.returncode:
        raise RuntimeError(f"OpenBao read failed: {r.stderr.strip()[-200:]}")
    return json.loads(r.stdout)["data"]["data"]


class _FTP4(ftplib.FTP_TLS):
    """FTPS over IPv4 only. agent-lxc has no IPv6 route, so an AAAA record
    gives an instant Errno 101 that hides what IPv4 did; the error names the
    address that failed."""

    def connect(self, host="", port=0, timeout=-999, source_address=None):
        self.host, self.port = host, port or 21
        if timeout != -999:
            self.timeout = timeout
        addrs = sorted({a[4][0] for a in socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)})
        errors = []
        for ip in addrs:
            try:
                self.sock = socket.create_connection((ip, self.port), self.timeout)
                break
            except OSError as e:
                errors.append(f"{ip}:{self.port} {type(e).__name__}: {e}")
        else:
            raise OSError(f"{self.host}: no IPv4 address answered ({'; '.join(errors) or 'no A record'})")
        self.af = self.sock.family
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome


def collect_plesk() -> int:
    d = _plesk_creds()
    ftp = _FTP4(timeout=60)
    try:
        ftp.connect(d["host"], 21)
        ftp.login(d["username"], d["password"])
        ftp.prot_p()
        names = [n for n in ftp.nlst("/logs") if n.split("/")[-1].startswith(PLESK_LOG_PREFIXES)]
        by_day: dict[str, list[str]] = defaultdict(list)
        for name in names:
            base = name.split("/")[-1]
            # `.processed` is today's lines that Plesk's statistics already
            # read; it overlaps the live log, and _append deduplicates.
            if base.endswith((".statbuf", ".webstat")):
                continue
            buf = io.BytesIO()
            ftp.retrbinary(f"RETR /logs/{base}", buf.write)
            raw = buf.getvalue()
            text = gzip.decompress(raw).decode("utf-8", "replace") if base.endswith(".gz") else raw.decode("utf-8", "replace")
            for ln in text.splitlines():
                rec = parse_combined(ln)
                if rec:
                    by_day[rec["ts"][:10]].append(ln)
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            pass
    return _append(PLESK_SITE, by_day)


# ---- Plesk backoff: every attempt counts, failures stop the pulls

PLESK_STATE = STATE / "plesk-attempts.json"


def plesk_state() -> dict:
    try:
        return json.loads(PLESK_STATE.read_text())
    except (OSError, ValueError):
        return {"last_attempt": 0, "failures": 0, "last_ok": None, "last_error": None}


def plesk_due(st: dict, now: float | None = None) -> tuple[bool, str]:
    now = time.time() if now is None else now
    if st.get("failures", 0) >= PLESK_MAX_FAILURES:
        return False, (f"stopped after {st['failures']} failures (last: {st.get('last_error')}); "
                       "run `secreport plesk-reset` once the cause is gone")
    age_h = (now - st.get("last_attempt", 0)) / 3600
    if age_h < PLESK_MIN_HOURS:
        return False, f"skipped: last attempt {age_h:.0f} h ago"
    return True, ""


def collect_plesk_guarded() -> int | str:
    st = plesk_state()
    due, why = plesk_due(st)
    if not due:
        return why
    st["last_attempt"] = time.time()
    try:
        n = collect_plesk()
        st.update(failures=0, last_ok=dt.datetime.now(dt.timezone.utc).isoformat(), last_error=None)
        return n
    except Exception as e:  # noqa: BLE001
        st["failures"] = st.get("failures", 0) + 1
        st["last_error"] = f"{type(e).__name__}: {e}"[:300]
        return f"error ({st['failures']}/{PLESK_MAX_FAILURES}): {st['last_error']}"
    finally:
        PLESK_STATE.write_text(json.dumps(st, indent=1))


def plesk_reset() -> None:
    PLESK_STATE.unlink(missing_ok=True)


# ---- retention

def prune(now: dt.date | None = None) -> dict[str, int]:
    """Delete cached request lines after CACHE_DAYS and weekly reports after
    REPORT_WEEKS (by the date in the file name)."""
    today = now or dt.date.today()
    gone = {"cache": 0, "reports": 0}
    for f in CACHE.glob("*/*.log") if CACHE.exists() else []:
        try:
            if (today - dt.date.fromisoformat(f.stem)).days > CACHE_DAYS:
                f.unlink()
                gone["cache"] += 1
        except ValueError:
            continue
    for f in list(STATE.glob("????-??-??.html")) + list(STATE.glob("????-??-??.json")):
        try:
            if (today - dt.date.fromisoformat(f.stem)).days > REPORT_WEEKS * 7:
                f.unlink()
                gone["reports"] += 1
        except ValueError:
            continue
    return gone


def collect() -> dict:
    STATE.mkdir(parents=True, exist_ok=True)
    res: dict = {"at": dt.datetime.now(dt.timezone.utc).isoformat()}
    res["k8s"] = collect_k8s()
    res[PLESK_SITE] = collect_plesk_guarded()
    res["bao"] = renew_bao_token()
    res["pruned"] = prune()
    (STATE / "collect-last.json").write_text(json.dumps(res, indent=1))
    return res


# ------------------------------------------------------------------ parsing

COMBINED = re.compile(
    r'^(?P<ip>\S+) \S+ (?P<user>\S+) \[(?P<t>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+)[^"]*" '
    r'(?P<status>\d{3}) \S+ "[^"]*" "(?P<ua>[^"]*)"(?: "(?P<xff>[^"]*)")?')
K8S_PREFIX = re.compile(r"^\[(?P<pod>[^\]]+)\] (?P<kts>\S+) (?P<rest>.*)$")
OAUTH2 = re.compile(
    r'^(?P<remote>\S+) - (?P<reqid>\S+) - (?P<user>.+?) \[(?P<t>[^\]]+)\] (?P<host>\S+) (?P<method>\S+) '
    r'(?P<upstream>\S+) "(?P<path>[^"]*)" (?P<proto>\S+) "(?P<ua>[^"]*)" (?P<status>\d{3})')
UVICORN = re.compile(r'^INFO:\s+(?P<ip>[\d.]+):\d+ - "(?P<method>\S+) (?P<path>\S+) [^"]*" (?P<status>\d{3})')
KC_EVENT = re.compile(r'type="(?P<type>[A-Z_]+)".*?realmName="(?P<realm>[^"]*)".*?clientId="(?P<client>[^"]*)"'
                      r'.*?ipAddress="(?P<ip>[^"]*)"(?:.*?error="(?P<error>[^"]*)")?(?:.*?username="(?P<username>[^"]*)")?')


def _ts_combined(t: str) -> str:
    return dt.datetime.strptime(t, "%d/%b/%Y:%H:%M:%S %z").astimezone(dt.timezone.utc).isoformat()


def parse_combined(ln: str) -> dict | None:
    m = COMBINED.match(ln)
    if not m:
        return None
    ip = m["ip"]
    if m["xff"] and m["xff"] != "-":       # convergence nginx: real client in the last field
        ip = m["xff"].split(",")[0].strip()
    return {"ts": _ts_combined(m["t"]), "ip": ip, "method": m["method"], "path": m["path"],
            "status": int(m["status"]), "ua": m["ua"], "user": None}


def parse_line(fmt: str, ln: str) -> dict | None:
    if fmt == "plesk":
        return parse_combined(ln)
    p = K8S_PREFIX.match(ln)
    if not p:
        return None
    kts, rest = p["kts"], p["rest"]
    ts = kts[:19] + "+00:00"
    if fmt == "combined":
        r = parse_combined(rest)
        if r:
            r["ts"] = ts
        return r
    if fmt == "oauth2proxy":
        m = OAUTH2.match(rest)
        if not m:
            return None
        user = m["user"].strip()
        return {"ts": ts, "ip": None, "method": m["method"], "path": m["path"], "status": int(m["status"]),
                "ua": m["ua"], "user": None if user in ("-", "") else user, "upstream": m["upstream"]}
    if fmt == "uvicorn":
        m = UVICORN.match(rest)
        if not m:
            return None
        return {"ts": ts, "ip": None, "method": m["method"], "path": m["path"], "status": int(m["status"]),
                "ua": None, "user": None}
    if fmt == "wanderer":
        try:
            j = json.loads(rest)
        except ValueError:
            return None
        if j.get("msg") != "http.request":
            return None
        return {"ts": ts, "ip": None, "method": j.get("method"), "path": j.get("path"),
                "status": int(j.get("status", 0)), "ua": None, "user": None}
    if fmt == "keycloak":
        m = KC_EVENT.search(rest)
        if not m:
            return None
        return {"ts": ts, "event": m["type"], "realm": m["realm"], "client": m["client"], "ip": m["ip"],
                "error": m["error"], "username": m["username"]}
    return None


# ------------------------------------------------------------------ classifying

AI_CRAWLERS = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "Claude-SearchBot",
               "anthropic-ai", "CCBot", "PerplexityBot", "Perplexity-User", "Bytespider", "Google-Extended",
               "Applebot-Extended", "meta-externalagent", "meta-externalfetcher", "FacebookBot", "Amazonbot",
               "cohere-ai", "Diffbot", "YouBot", "Timpibot", "ImagesiftBot", "omgili", "AI2Bot", "PetalBot",
               "Kangaroo Bot", "TikTokSpider", "DuckAssistBot", "MistralAI-User", "Panscient", "QualifiedBot"]
SEARCH = ["Googlebot", "bingbot", "DuckDuckBot", "YandexBot", "Baiduspider", "Applebot", "SeznamBot",
          "Qwantbot", "Qwant", "Ecosia", "Sogou", "Exabot", "Google-InspectionTool", "GoogleOther",
          "Storebot-Google", "AdsBot-Google", "Mediapartners-Google", "MojeekBot", "Yahoo! Slurp"]
SEO = ["AhrefsBot", "SemrushBot", "MJ12bot", "DotBot", "DataForSeoBot", "BLEXBot", "serpstatbot", "SeekportBot",
       "Barkrowler", "ZoominfoBot", "rogerbot", "Screaming Frog", "ChromeStats", "Linkfluence", "Twitterbot",
       "facebookexternalhit", "LinkedInBot", "Slackbot", "WhatsApp", "TelegramBot", "Discordbot"]
SCANNERS = ["zgrab", "Nuclei", "masscan", "CensysInspect", "Censys", "Expanse", "Palo Alto", "l9explore", "l9tcpid",
            "InternetMeasurement", "ModatScanner", "Shodan", "Nmap", "httpx", "Go-http-client", "python-requests",
            "python-httpx", "aiohttp", "curl/", "Wget", "libwww-perl", "okhttp", "Odin", "NetcraftSurveyAgent",
            "CyberOK", "WellKnownBot", "LeakIX", "BitSightBot", "Keydrop", "fasthttp", "Hello World", "Mozlila",
            "abuse.xmco", "Detectify", "Qualys", "Nessus", "sqlmap", "Nikto", "WPScan", "Fuzz Faster"]
SERVICES = ["GitHub-Hookshot", "UptimeRobot", "Pingdom", "StatusCake", "Better Uptime", "Cloudflare-Healthchecks",
            "Cloudflare-Traffic-Manager", "kube-probe"]

SCANNER_PATHS = re.compile(
    r"(wp-(admin|login|content|includes)|xmlrpc\.php|/\.env|/\.git|/\.svn|/\.hg|/\.aws|/\.ssh|/\.DS_Store|"
    r"phpmyadmin|pma/|/phpinfo|\.php\b|/cgi-bin|/actuator|/server-status|/config\.(json|js|yml|yaml)|"
    r"/\.vscode|/backup|\.sql\b|\.bak\b|/admin|/console|/boaform|/HNAP1|/owa/|/autodiscover|/ecp/|"
    r"/vendor/phpunit|/solr|/jenkins|/manager/html|/\.well-known/(?!security\.txt|openid|acme))", re.I)


def classify_ua(ua: str | None) -> tuple[str, str]:
    if not ua or ua == "-":
        return "leeg", "(geen user-agent)"
    for cat, names in (("webhook/monitor", SERVICES), ("AI-crawler", AI_CRAWLERS), ("zoekmachine", SEARCH), ("SEO/preview", SEO), ("scanner/tool", SCANNERS)):
        for n in names:
            if n.lower() in ua.lower():
                return cat, n
    if re.search(r"bot|crawl|spider|scan", ua, re.I):
        return "overige bot", ua[:60]
    return "browser/onbekend", ua[:60]


# ------------------------------------------------------------------ summarising

PUBLIC_OK = re.compile(r"^/(health|ping|robots\.txt|favicon\.ico|oauth2/.*|ui/login.*|ui/static/.*|ui/oauth/.*)(\?.*)?$")


def _windows() -> list[tuple[str, str]]:
    f = STATE / "selfscan-windows.json"
    return [tuple(w) for w in json.loads(f.read_text())] if f.exists() else []


def _in_window(ts: str, wins) -> bool:
    return any(a <= ts <= b for a, b in wins)


def load(site: str, fmt: str, since: dt.datetime, until: dt.datetime) -> list[dict]:
    recs = []
    d = since.date()
    while d <= until.date():
        f = CACHE / site / f"{d.isoformat()}.log"
        if f.exists():
            for ln in f.read_text(errors="replace").splitlines():
                r = parse_line(fmt, ln)
                if r and since.isoformat() <= r["ts"] < until.isoformat():
                    recs.append(r)
        d += dt.timedelta(days=1)
    return recs


def summarize_requests(recs: list[dict], site: str, wins) -> dict:
    own = 0
    keep = []
    for r in recs:
        if (r.get("ua") and "westerweel-selfscan" in r["ua"]) or (r.get("ua") is None and _in_window(r["ts"], wins)):
            own += 1
            continue
        keep.append(r)
    status = Counter(f"{r['status'] // 100}xx" for r in keep)
    not_found = Counter(r["path"].split("?")[0][:120] for r in keep if r["status"] in (404, 410))
    scanner_hits = Counter(r["path"].split("?")[0][:120] for r in keep if SCANNER_PATHS.search(r["path"]))
    scanner_ok = sorted({f"{r['status']} {r['path'][:120]}" for r in keep
                         if SCANNER_PATHS.search(r["path"]) and 200 <= r["status"] < 300})
    uas = Counter()
    cats = Counter()
    for r in keep:
        if r.get("ua") is not None:
            cat, name = classify_ua(r["ua"])
            uas[(cat, name)] += 1
            cats[cat] += 1
    ips = Counter(r["ip"] for r in keep if r.get("ip"))
    asn, country = geo.aggregate(ips)
    out = {
        "requests": len(keep), "own_requests_excluded": own,
        "status": dict(sorted(status.items())),
        "top_not_found": not_found.most_common(15),
        "scanner_paths": scanner_hits.most_common(15),
        "scanner_paths_2xx": scanner_ok[:20],
        "ua_categories": cats.most_common(),
        "top_user_agents": [[c, n, k] for (c, n), k in uas.most_common(15)],
        "top_asn": asn[:10], "top_countries": country[:10],
        "has_ip": bool(ips), "has_ua": any(r.get("ua") is not None for r in recs),
    }
    # What got past the login / reached an API without auth.
    users = Counter(r["user"] for r in keep if r.get("user"))
    if site == "wordsworth":
        out["authenticated_users"] = users.most_common()
        out["unauth_2xx_upstream"] = Counter(
            f"{r['method']} {r['path'].split('?')[0][:100]}" for r in keep
            if not r.get("user") and 200 <= r["status"] < 300 and not PUBLIC_OK.match(r["path"])).most_common(15)
    elif site in ("netnl-api", "wanderer"):
        out["api_2xx"] = Counter(f"{r['method']} {re.sub(r'[0-9a-f]{16,}', '<id>', r['path'].split('?')[0])[:100]}"
                                 for r in keep if 200 <= r["status"] < 300 and not PUBLIC_OK.match(r["path"])
                                 ).most_common(15)
    return out


def summarize_keycloak(recs: list[dict], wins) -> dict:
    recs = [r for r in recs if not (r.get("username") or "").startswith("selfscan-")
            and not _in_window(r["ts"], wins)]
    errs = [r for r in recs if r["event"].endswith("_ERROR")]
    return {
        "events": len(recs),
        "login_errors_by_realm": Counter(r["realm"] for r in errs).most_common(),
        "login_errors_by_error": Counter(r["error"] for r in errs).most_common(),
        "login_errors_by_client": Counter(f"{r['realm']}/{r['client']}" for r in errs).most_common(10),
        "usernames_tried": Counter(r["username"] for r in errs if r.get("username")).most_common(10),
        "ips_note": "ipAddress is the first X-Forwarded-For value, which the client controls (see kc-xff-trust)",
        "top_ips": Counter(r["ip"] for r in errs).most_common(10),
    }


def summarize(since: dt.datetime, until: dt.datetime) -> dict:
    wins = _windows()
    out = {}
    sources = [(PLESK_SITE, "plesk")] + [(s.site, s.fmt) for s in K8S_LOGS]
    for site, fmt in sources:
        recs = load(site, fmt, since, until)
        days = sorted({p.stem for p in (CACHE / site).glob("*.log")}) if (CACHE / site).exists() else []
        cover = [d for d in days if since.date().isoformat() <= d <= until.date().isoformat()]
        if fmt == "keycloak":
            out[site + "-events"] = {"source": "keycloak events (pod log)", "days_covered": cover,
                                     **summarize_keycloak(recs, wins)}
        else:
            out[site] = {"source": {"plesk": "Plesk access_ssl_log + access_log (FTPS)",
                                    "oauth2proxy": "oauth2-proxy request log", "uvicorn": "uvicorn access log",
                                    "wanderer": "wanderer http.request log", "combined": "nginx access log"}[fmt],
                         "days_covered": cover, **summarize_requests(recs, site, wins)}
    return out
