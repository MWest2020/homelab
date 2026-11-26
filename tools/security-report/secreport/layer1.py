"""Layer 1: passive and safe, against every public hostname. One scanner at a
time, each in its own memory-capped scope, all rate-limited.

- security headers + cookie flags (one GET per site, plus security.txt)
- TLS with sslyze (CLI, JSON out)
- ZAP baseline: spider for ZAP_SPIDER_MINUTES, passive rules only; the active
  scanner is never started
- nuclei with filtered templates: include tags, exclude tags and directories,
  and a check of every template file (GET/HEAD only, nothing self-contained,
  nothing out-of-band); see the nuclei section
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from .config import (FUNNEL_HOSTS, NUCLEI_CONCURRENCY, NUCLEI_RATE, SITES, STATE, TOOLS, USER_AGENT,
                     ZAP_SPIDER_MINUTES)
from .util import capped, client, stop_scopes

WANT_HEADERS = {
    "strict-transport-security": "HSTS",
    "content-security-policy": "CSP",
    "x-content-type-options": "X-Content-Type-Options",
    "referrer-policy": "Referrer-Policy",
    "permissions-policy": "Permissions-Policy",
}


# ------------------------------------------------------------------ headers

# A handful of the paths scanners try most, one request per second per site:
# a 200 that isn't an HTML page (a SPA fallback) is a leak.
EXPOSURE_PATHS = ["/.git/config", "/.env", "/.DS_Store", "/server-status", "/.htaccess"]

def headers() -> list[dict]:
    out = []
    with client(follow_redirects=True, max_redirects=6) as c:
        for s in SITES:
            row = {"site": s.name, "url": s.url}
            try:
                r = c.get(s.url)
                h = {k.lower(): v for k, v in r.headers.items()}
                missing = [name for k, name in WANT_HEADERS.items() if k not in h]
                csp = h.get("content-security-policy", "")
                if "x-frame-options" not in h and "frame-ancestors" not in csp:
                    missing.append("X-Frame-Options/frame-ancestors")
                cookies = []
                for raw in r.headers.get_list("set-cookie"):
                    low = raw.lower()
                    flags = [f for f, ok in (("Secure", "secure" in low), ("HttpOnly", "httponly" in low),
                                             ("SameSite", "samesite" in low)) if not ok]
                    if flags:
                        cookies.append(f"{raw.split('=')[0]}: mist {', '.join(flags)}")
                leak = {k: h[k] for k in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version", "x-generator")
                        if k in h}
                if leak.get("server") in ("cloudflare", "GitHub.com"):
                    del leak["server"]
                time.sleep(0.5)
                st = c.get(urllib.parse.urljoin(r.url.__str__(), "/.well-known/security.txt"))
                exposed = []
                for path in EXPOSURE_PATHS:
                    time.sleep(1)
                    x = c.get(urllib.parse.urljoin(str(r.url), path), follow_redirects=False)
                    if x.status_code == 200 and len(x.content) > 0 and not x.headers.get("content-type", "").startswith("text/html"):
                        exposed.append(f"{path} → 200 ({len(x.content)} bytes)")
                row.update({"final_url": str(r.url), "status": r.status_code, "missing": missing, "exposed_files": exposed,
                            "hsts": h.get("strict-transport-security"), "cookies": cookies, "banner": leak,
                            "security_txt": st.status_code == 200 and "contact:" in st.text.lower()})
            except Exception as e:  # noqa: BLE001
                row["error"] = f"{type(e).__name__}: {e}"[:200]
            out.append(row)
            time.sleep(0.5)
    return out


# ------------------------------------------------------------------ TLS

TLS_FLAGS = ["--sslv2", "--sslv3", "--tlsv1", "--tlsv1_1", "--tlsv1_2", "--tlsv1_3", "--certinfo",
             "--heartbleed", "--robot", "--openssl_ccs", "--compression", "--reneg", "--elliptic_curves",
             "--http_headers"]


def tls(workdir: Path) -> list[dict]:
    """sslyze, one host at a time with its own time limit: a host that drops
    some handshakes (and makes sslyze wait out every timeout) must not hold up
    the rest."""
    hosts = sorted({urllib.parse.urlparse(s.url).hostname for s in SITES if s.tls and not s.tls_light})
    results, errors = [], []
    for host in hosts:
        jf = workdir / f"sslyze-{host}.json"
        jf.unlink(missing_ok=True)
        try:
            subprocess.run(capped([sys.executable, "-m", "sslyze", f"--json_out={jf}", "--quiet", *TLS_FLAGS, host], "sslyze"),
                           capture_output=True, text=True, timeout=420)
        except subprocess.TimeoutExpired:
            errors.append({"host": host, "error": "sslyze timeout (7 min)"})
            continue
        if jf.exists():
            results += json.loads(jf.read_text()).get("server_scan_results", [])
        else:
            errors.append({"host": host, "error": "sslyze gaf geen resultaat"})
    data = {"server_scan_results": results}
    out = []
    for srv in data.get("server_scan_results", []):
        host = srv["server_location"]["hostname"]
        row = {"host": host, "status": srv.get("scan_status")}
        res = srv.get("scan_result") or {}

        def accepted(key):
            r = (res.get(key) or {}).get("result") or {}
            return [c["cipher_suite"]["name"] for c in r.get("accepted_cipher_suites", [])]

        protos = {k: bool(accepted(k)) for k in ("ssl_2_0_cipher_suites", "ssl_3_0_cipher_suites",
                                                 "tls_1_0_cipher_suites", "tls_1_1_cipher_suites",
                                                 "tls_1_2_cipher_suites", "tls_1_3_cipher_suites")}
        row["protocols"] = [k.replace("_cipher_suites", "").replace("_", ".").upper().replace("SSL.", "SSL ").replace("TLS.", "TLS ")
                            for k, v in protos.items() if v]
        row["old_protocols"] = [p for p in row["protocols"] if p.startswith(("SSL", "TLS 1.0", "TLS 1.1"))]
        weak = [c for c in accepted("tls_1_2_cipher_suites")
                if any(w in c for w in ("_CBC_", "RC4", "3DES", "NULL", "EXPORT")) or c.startswith("TLS_RSA_")]
        row["weak_tls12_ciphers"] = weak
        try:
            dep = res["certificate_info"]["result"]["certificate_deployments"][0]
            leaf = dep["received_certificate_chain"][0]
            row["cert_not_after"] = leaf.get("not_valid_after")
            row["cert_issuer"] = (leaf.get("issuer") or {}).get("rfc4514_string")
            row["chain_trusted"] = all(v.get("was_validation_successful") for v in dep.get("path_validation_results", []))
            row["hostname_match"] = dep.get("leaf_certificate_subject_matches_hostname")
        except (KeyError, IndexError, TypeError):
            pass
        vulns = []
        for key, flag in (("heartbleed", "is_vulnerable_to_heartbleed"), ("openssl_ccs_injection", "is_vulnerable_to_ccs_injection")):
            if ((res.get(key) or {}).get("result") or {}).get(flag):
                vulns.append(key)
        robot = ((res.get("robot") or {}).get("result") or {}).get("robot_result", "")
        if "VULNERABLE" in str(robot) and "NOT_VULNERABLE" not in str(robot):
            vulns.append(f"ROBOT {robot}")
        if ((res.get("tls_compression") or {}).get("result") or {}).get("supports_compression"):
            vulns.append("CRIME (TLS compression)")
        reneg = (res.get("session_renegotiation") or {}).get("result") or {}
        if reneg.get("is_vulnerable_to_client_renegotiation_dos"):
            vulns.append("client-initiated renegotiation")
        if reneg and not reneg.get("supports_secure_renegotiation", True):
            vulns.append("no secure renegotiation")
        row["vulnerabilities"] = vulns
        hh = ((res.get("http_headers") or {}).get("result") or {}).get("strict_transport_security_header")
        row["hsts_max_age"] = (hh or {}).get("max_age")
        out.append(row)
    light = [tls_light(urllib.parse.urlparse(s.url).hostname) for s in SITES if s.tls and s.tls_light]
    return out + light + errors


def tls_light(host: str) -> dict:
    """For shared hosting: one handshake per protocol version, a second apart,
    plus the certificate. No cipher enumeration, no ROBOT."""
    import datetime as dt
    import socket
    import ssl
    row = {"host": host, "light": True, "protocols": [], "weak_tls12_ciphers": [], "vulnerabilities": []}
    versions = [("TLS 1.0", ssl.TLSVersion.TLSv1), ("TLS 1.1", ssl.TLSVersion.TLSv1_1),
                ("TLS 1.2", ssl.TLSVersion.TLSv1_2), ("TLS 1.3", ssl.TLSVersion.TLSv1_3)]
    for name, v in versions:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
            ctx.minimum_version = ctx.maximum_version = v
            with socket.create_connection((host, 443), timeout=10) as sock, ctx.wrap_socket(sock, server_hostname=host):
                row["protocols"].append(name)
        except (OSError, ssl.SSLError, ValueError):
            pass
        time.sleep(1)
    row["old_protocols"] = [p for p in row["protocols"] if p in ("TLS 1.0", "TLS 1.1")]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock, ctx.wrap_socket(sock, server_hostname=host) as t:
            cert = t.getpeercert()
        row["chain_trusted"] = row["hostname_match"] = True
        row["cert_not_after"] = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").date().isoformat()
        row["cert_issuer"] = dict(x[0] for x in cert["issuer"]).get("organizationName")
    except ssl.SSLCertVerificationError as e:
        row["chain_trusted"] = False
        row["error"] = str(e)[:150]
    except OSError as e:
        row["error"] = f"geen verbinding: {e}"[:150]
    if not row["protocols"] and "error" in row:
        row.pop("chain_trusted", None)
    return row


# ------------------------------------------------------------------ ZAP baseline (passive)

def zap(workdir: Path) -> dict:
    if not (TOOLS / "zap").exists():
        return {"status": "skipped", "reason": "ZAP niet geïnstalleerd (install-scanners.sh)"}
    from zapv2 import ZAPv2

    home = workdir / "zap-home"
    home.mkdir(parents=True, exist_ok=True)
    jar = next(iter(sorted((TOOLS / "zap").glob("zap-*.jar"))), None)
    if jar is None:
        return {"status": "skipped", "reason": "zap-*.jar niet gevonden"}
    key = secrets.token_hex(16)
    port = 8091
    log = open(workdir / "zap.log", "w")
    # java directly, not zap.sh: zap.sh picks its own -Xmx (a quarter of RAM),
    # which would break the 1500M scope. ZAP listens on 127.0.0.1 only, so the
    # API may accept any Host header (the Python client sends "zap").
    stop_scopes("zap")   # a ZAP left over from an aborted run would hold the port
    proc = subprocess.Popen(capped(["java", "-Xmx768m", "-jar", str(jar), "-daemon", "-host", "127.0.0.1",
                                    "-port", str(port), "-dir", str(home), "-config", f"api.key={key}",
                                    "-config", "api.addrs.addr.name=.*", "-config", "api.addrs.addr.regex=true",
                                    "-silent"], "zap"),
                            cwd=str(TOOLS / "zap"), stdout=log, stderr=subprocess.STDOUT)
    z = ZAPv2(apikey=key, proxies={"http": f"http://127.0.0.1:{port}", "https": f"http://127.0.0.1:{port}"})
    try:
        for _ in range(180):
            try:
                z.core.version
                break
            except Exception:  # noqa: BLE001
                if proc.poll() is not None:
                    return {"status": "error", "reason": "ZAP stopte bij het opstarten (zie zap.log)"}
                time.sleep(2)
        else:
            return {"status": "error", "reason": "ZAP startte niet binnen 6 minuten"}
        z.core.set_option_default_user_agent(USER_AGENT)
        z.spider.set_option_max_duration(ZAP_SPIDER_MINUTES)
        z.spider.set_option_thread_count(2)
        z.spider.set_option_max_depth(5)
        # Never submit forms: a baseline only follows links.
        z.spider.set_option_post_form(False)
        z.spider.set_option_process_form(False)
        results = {}
        for s in SITES:
            if not s.deep:
                continue
            z.core.access_url(url=s.url, followredirects=True)
            sid = z.spider.scan(url=s.url, recurse=True, subtreeonly=False)
            t0 = time.time()
            while time.time() - t0 < ZAP_SPIDER_MINUTES * 60 + 60:
                try:
                    if int(z.spider.status(sid)) >= 100:
                        break
                except ValueError:
                    break
                time.sleep(3)
            z.spider.stop(sid)
            for _ in range(120):
                if int(z.pscan.records_to_scan) == 0:
                    break
                time.sleep(2)
            host = urllib.parse.urlparse(s.url).netloc
            alerts = z.core.alerts(baseurl=f"{urllib.parse.urlparse(s.url).scheme}://{host}")
            agg: dict[tuple, dict] = {}
            for a in alerts:
                k = (a["risk"], a["alert"])
                e = agg.setdefault(k, {"risk": a["risk"], "alert": a["alert"], "count": 0, "example": a["url"],
                                       "pluginId": a.get("pluginId")})
                e["count"] += 1
            order = {"High": 0, "Medium": 1, "Low": 2, "Informational": 3}
            results[s.name] = sorted(agg.values(), key=lambda e: (order.get(e["risk"], 9), e["alert"]))
            z.core.delete_all_alerts()
        return {"status": "ok", "sites": results}
    finally:
        try:
            z.core.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
        log.close()


# ------------------------------------------------------------------ nuclei (filtered templates)
#
# Three filters, all must pass:
# 1. directories: only http/ and ssl/, minus the ones full of active checks;
# 2. tags: an include list, and an exclude list (note `instrusive`, a typo
#    that real templates carry);
# 3. the template file itself: no state-changing method, no raw POST/PUT/
#    DELETE/PATCH, no self-contained template (those request third parties),
#    no OOB/interactsh, no unsafe raw requests, no code/javascript/headless/flow.
# tests/test_nuclei_safe.py runs `nuclei -tl` with exactly these arguments and
# fails if anything unsafe gets through.

NUCLEI_TAGS = "exposure,misconfig,config,ssl,cors,disclosure,keys,token,panel,redirect,takeover,headers"
NUCLEI_EXCLUDE_TAGS = ("intrusive,instrusive,dos,fuzz,fuzzing,bruteforce,brute-force,default-login,oast,oob,rce,sqli,"
                       "xss,lfi,ssrf,file-upload,deserialization,injection,cve,vuln,bypass,auth-bypass,backdoor,"
                       "unauth,register,signup,graphql")
NUCLEI_EXCLUDE_DIRS = ("http/vulnerabilities", "http/cves", "http/cnvd", "http/iot")
NUCLEI_EXCLUDE_TYPES = "headless,code,javascript,workflow,file,tcp,dns,whois,websocket"

_UNSAFE = [
    ("self-contained", re.compile(r"(?m)^\s*self-contained:\s*true")),
    ("state-changing method", re.compile(r"(?mi)^\s*-?\s*method:\s*(POST|PUT|DELETE|PATCH)\b")),
    ("raw state-changing request", re.compile(r"(?m)^\s*\|?\s*(POST|PUT|DELETE|PATCH) \S+ HTTP/\d")),
    ("unsafe raw request", re.compile(r"(?m)^\s*unsafe:\s*true")),
    ("out-of-band", re.compile(r"interactsh")),
    ("non-http protocol", re.compile(r"(?m)^(code|javascript|headless|flow):")),
]


def unsafe_reason(template: Path) -> str | None:
    text = template.read_text(errors="replace")
    for why, rx in _UNSAFE:
        if rx.search(text):
            return why
    return None


def nuclei_filter_args(templates: Path) -> list[str]:
    # The directory exclusion is done by not passing those directories (see
    # template_dirs); nuclei's -et on a directory costs ~30 s per directory.
    return ["-tags", NUCLEI_TAGS, "-etags", NUCLEI_EXCLUDE_TAGS, "-ept", NUCLEI_EXCLUDE_TYPES]


def template_dirs(templates: Path) -> list[Path]:
    """http/<subdir> for every subdir not excluded, plus ssl/."""
    excluded = {templates / d for d in NUCLEI_EXCLUDE_DIRS}
    dirs = [d for d in sorted((templates / "http").iterdir()) if d.is_dir() and d not in excluded]
    return dirs + [templates / "ssl"]


def _excluded_dir(t: Path, templates: Path) -> bool:
    return any(str(t).startswith(f"{templates / d}/") for d in NUCLEI_EXCLUDE_DIRS)


def list_templates(binary: Path, templates: Path, template_args: list[str], home: Path) -> list[Path]:
    p = subprocess.run([str(binary), "-duc", "-silent", "-nc", "-tl", *template_args, *nuclei_filter_args(templates)],
                       capture_output=True, text=True, timeout=600, env={**os.environ, "HOME": str(home)},
                       stdin=subprocess.DEVNULL)   # nuclei reads targets from a stdin that isn't a tty
    return [Path(ln.strip()) for ln in p.stdout.splitlines() if ln.strip().endswith((".yaml", ".yml"))]


def select_templates(binary: Path, templates: Path, home: Path) -> dict[str, list[Path]]:
    args = [a for d in template_dirs(templates) for a in ("-t", str(d))]
    listed = list_templates(binary, templates, args, home)
    safe = [t for t in listed if t.exists() and not _excluded_dir(t, templates) and unsafe_reason(t) is None]
    return {"http": [t for t in safe if f"{templates}/http/" in str(t)],
            "ssl": [t for t in safe if f"{templates}/ssl/" in str(t)],
            "dropped": len(listed) - len(safe)}


def nuclei(workdir: Path) -> dict:
    binary, templates = TOOLS / "bin/nuclei", TOOLS / "nuclei-templates"
    if not binary.exists() or not templates.exists():
        return {"status": "skipped", "reason": "nuclei niet geïnstalleerd (install-scanners.sh)"}
    sel = select_templates(binary, templates, workdir)
    out = workdir / "nuclei.jsonl"
    out.unlink(missing_ok=True)
    env = {**os.environ, "HOME": str(workdir)}   # keep nuclei's config/cache out of ~
    runs = [
        # http templates against every deep site
        ("http", sel["http"], [s.url for s in SITES if s.deep]),
        # ssl templates only where the TLS end is ours (not github.io)
        ("ssl", sel["ssl"], [s.url for s in SITES if s.deep and s.tls]),
    ]
    status, stderr = [], ""
    for name, tmpl, urls in runs:
        if not tmpl or not urls:
            continue
        tl, tg = workdir / f"nuclei-{name}-templates.txt", workdir / f"nuclei-{name}-targets.txt"
        tl.write_text("\n".join(map(str, tmpl)) + "\n")
        tg.write_text("\n".join(urls) + "\n")
        part = workdir / f"nuclei-{name}.jsonl"
        part.unlink(missing_ok=True)
        cmd = capped([str(binary), "-duc", "-ni", "-silent", "-nc", "-jsonl", "-o", str(part), "-l", str(tg),
                      "-t", str(tl), *nuclei_filter_args(templates),
                      "-rl", str(NUCLEI_RATE), "-c", str(NUCLEI_CONCURRENCY), "-bs", str(NUCLEI_CONCURRENCY),
                      "-timeout", "10", "-retries", "1", "-H", f"User-Agent: {USER_AGENT}",
                      "-ud", str(templates), "-disable-update-check"], f"nuclei-{name}")
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=4 * 3600, env=env, stdin=subprocess.DEVNULL)
        status.append(f"{name}: {'ok' if p.returncode == 0 else f'exit {p.returncode}'} ({len(tmpl)} templates)")
        if p.returncode:
            stderr += p.stderr[-300:]
        if part.exists():
            with out.open("a") as fh:
                fh.write(part.read_text())
    findings = []
    if out.exists():
        for ln in out.read_text().splitlines():
            try:
                j = json.loads(ln)
            except ValueError:
                continue
            findings.append({"template": j.get("template-id"), "name": (j.get("info") or {}).get("name"),
                             "severity": (j.get("info") or {}).get("severity"), "host": j.get("host"),
                             "matched": j.get("matched-at"), "extracted": (j.get("extracted-results") or [])[:3]})
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), f["host"] or "", f["template"] or ""))
    return {"status": "; ".join(status) or "niets te doen", "count": len(findings), "findings": findings,
            "templates_dropped_by_file_check": sel["dropped"], "stderr_tail": stderr}


# ------------------------------------------------------------------ funnel exposure

def funnel_dns() -> list[dict]:
    out = []
    for h in FUNNEL_HOSTS:
        p = subprocess.run(["dig", "+short", "A", h, "@1.1.1.1"], capture_output=True, text=True, timeout=30)
        ips = [x for x in p.stdout.split() if x[0].isdigit()]
        out.append({"host": h, "public_dns": ips})
    return out


def run(skip: set[str]) -> dict:
    workdir = STATE / "work"
    workdir.mkdir(parents=True, exist_ok=True)
    res: dict = {}
    steps = [("headers", headers), ("tls", lambda: tls(workdir)), ("zap", lambda: zap(workdir)),
             ("nuclei", lambda: nuclei(workdir)), ("funnel_dns", funnel_dns)]
    for name, fn in steps:
        if name in skip:
            res[name] = {"status": "skipped", "reason": "uitgezet voor deze run"}
            continue
        t0 = time.time()
        try:
            res[name] = fn()
        except Exception as e:  # noqa: BLE001
            res[name] = {"status": "error", "reason": f"{type(e).__name__}: {e}"[:300]}
        print(f"layer1 {name}: {time.time() - t0:.0f}s", file=sys.stderr)
    return res
