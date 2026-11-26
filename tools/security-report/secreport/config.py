"""What is in scope, and where things live.

Scope is Mark's own public surface only (Mark, 2026-11-25: all of his own infra
is test/development, active testing allowed). Tailnet-only services are out.
Never add a host that is not his: no employer or "conduction" orgs, no
Yourhosting systems beyond the bazibo.nl site, no other Cloudflare customers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
STATE = Path(os.environ.get("SECREPORT_STATE", HOME / ".local/state/security-report"))
TOOLS = Path(os.environ.get("SECREPORT_TOOLS", HOME / ".local/share/security-report"))
CACHE = STATE / "logs"           # collected request lines, one file per site per UTC day
CF_ENV = HOME / ".config/cloudflare/read.env"     # CLOUDFLARE_READ_TOKEN (read-only)
BAO_ENV = HOME / ".config/security-report/bao.env"  # BAO_TOKEN, policy `security-report`

# Every request we make carries this, so our own traffic can be told apart in
# logs that record the user-agent. Logs without a UA use the scan windows.
USER_AGENT = "westerweel-selfscan/1.0 (+weekly self-scan by Mark's agent; homelab tools/security-report)"

# Rate limits: polite for shared hosting (bazibo.nl) and GitHub Pages.
NUCLEI_RATE = 8          # requests/second, whole run
NUCLEI_CONCURRENCY = 4
ZAP_SPIDER_MINUTES = 1   # like zap-baseline.py
SCANNER_MEMORY = "1500M"

# Retention, enforced by every collect: the request-line cache and the weekly
# reports. Older files are deleted.
CACHE_DAYS = 35
REPORT_WEEKS = 26

# Hosts that are deliberately NOT scanned or reported as gaps, even though
# Cloudflare still lists them. billbird.westerweel.work: switched off by Mark
# on 2026-11-25; never probe it again (tests enforce that SITES excludes it).
EXCLUDED_HOSTS = frozenset({"billbird.westerweel.work"})

JUMPY = os.environ.get("SECREPORT_JUMPY", "jumpy")
TAILNET = os.environ.get("SECREPORT_TAILNET", "tail8f7877.ts.net")


@dataclass(frozen=True)
class Site:
    name: str                    # short key, used in file names
    url: str                     # entry URL for layer 1
    kind: str                    # cloudflare-tunnel | cloudflare-pages | plesk | github-pages | tailscale-funnel
    where: str                   # where it is configured (for the "gaps" column)
    tls: bool = True             # run the TLS scan (False when the TLS end is a shared provider)
    tls_light: bool = False      # shared hosting: 1 handshake per protocol instead of sslyze's enumeration
    deep: bool = True            # nuclei + ZAP (False: headers/TLS only)
    notes: str = ""


SITES: list[Site] = [
    Site("westerweel-work", "https://westerweel.work/", "cloudflare-pages",
         "Cloudflare Pages project westerweel-work (repo MWest2020/westerweel-work)"),
    Site("www-westerweel-work", "https://www.westerweel.work/", "cloudflare-pages",
         "Cloudflare Pages, CNAME www → westerweel-work.pages.dev", tls=False, deep=False),
    Site("iam", "https://iam.westerweel.work/realms/westerweel/account/", "cloudflare-tunnel",
         "homelab cluster-config/infra/keycloak (tunnel ingress remotely managed)"),
    Site("wordsworth", "https://wordsworth.westerweel.work/", "cloudflare-tunnel",
         "homelab cluster-config/infra/wordsworth (oauth2-proxy → wordsworth-api)"),
    Site("wanderer", "https://wanderer.westerweel.work/ui/", "cloudflare-tunnel",
         "homelab cluster-config/infra/wanderer"),
    Site("netnl-api", "https://api.westerweel.work/", "cloudflare-tunnel",
         "homelab cluster-config/infra/netnl"),
    Site("convergence", "https://convergence.westerweel.work/", "cloudflare-tunnel",
         "homelab cluster-config/infra/convergence"),
    # Shared hosting with a flood-sensitive firewall: on 2026-11-25 a full
    # sslyze run (hundreds of handshakes) got Mark's home IP blocked on the
    # whole server. So: a light TLS check, no nuclei/ZAP, exposure probes at
    # one request per second, and the FTPS log pull once a day.
    Site("bazibo-nl", "https://bazibo.nl/", "plesk",
         "Yourhosting Plesk web-1066, subscription bazibo.nl (runbook bazibo-nl)", tls_light=True, deep=False),
    Site("bazibo-ghpages", "https://mwest2020.github.io/bazibo/", "github-pages",
         "GitHub Pages of MWest2020/bazibo", tls=False,
         notes="TLS is GitHub's, shared with every github.io site: not ours to grade."),
]


@dataclass(frozen=True)
class K8sLogSource:
    site: str
    namespace: str
    selector: str
    container: str
    fmt: str                     # parser name in logs.py
    drop: tuple[str, ...] = field(default=())   # substrings of probe lines to drop at collect time


K8S_LOGS: list[K8sLogSource] = [
    K8sLogSource("wordsworth", "wordsworth", "app=wordsworth,component=auth", "oauth2-proxy",
                 "oauth2proxy", drop=("kube-probe/",)),
    K8sLogSource("wanderer", "wanderer", "app=wanderer,component=server", "wanderer",
                 "wanderer", drop=('"path":"/healthz"',)),
    K8sLogSource("netnl-api", "netnl", "app=netnl,component=facade", "facade",
                 "uvicorn", drop=('"GET /health HTTP',)),
    K8sLogSource("convergence", "convergence", "app=convergence", "web",
                 "combined", drop=("kube-probe/",)),
    K8sLogSource("iam", "keycloak", "app=keycloak,component=server", "keycloak",
                 "keycloak"),
]

# Tailscale Funnel ingresses (annotation tailscale.com/funnel=true). On
# 2026-11-25 these did not resolve in public DNS, so they are not public
# surface; the report checks that every week and flags it if it changes.
FUNNEL_HOSTS = [f"convergence.{TAILNET}", f"netnl.{TAILNET}"]

# Plesk: the subscription's logs/ directory over FTPS, read-only.
PLESK_SITE = "bazibo-nl"
PLESK_BAO_PATH = "kv/westerweel/bazibo-ftp"
PLESK_LOG_PREFIXES = ("access_ssl_log", "access_log")
PLESK_MIN_HOURS = 20        # at most one FTPS attempt a day (success or not): Plesk keeps five days
PLESK_MAX_FAILURES = 3      # then stop until `secreport plesk-reset`: failed logins can keep a firewall block alive

# Cloudflare zone (read-only token sees exactly this one).
CF_ZONE = "westerweel.work"
