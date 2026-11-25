"""Cloudflare analytics for the westerweel.work zone: what reaches the edge,
including traffic the origins never see (blocked or challenged).

Read-only token in ~/.config/cloudflare/read.env (CLOUDFLARE_READ_TOKEN). If
the file is missing this part is skipped, not failed. The token is never
printed or written anywhere.

Free plan limits (measured 2026-11-25): httpRequestsAdaptiveGroups has no
clientAsn/botScore (we map clientIP to an ASN locally); firewallEventsAdaptive
works, its Groups variant does not. Adaptive data is sampled: counts are
Cloudflare's estimates. Retention is 31 days, max range 30 days.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

import httpx

from . import geo
from .config import CF_ENV, CF_ZONE
from .logs import SCANNER_PATHS, classify_ua
from .util import iso, read_env

API = "https://api.cloudflare.com/client/v4"
OWN = "%westerweel-selfscan%"


class CF:
    def __init__(self, token: str):
        self.c = httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=60)

    def rest(self, path: str) -> dict:
        r = self.c.get(API + path)
        r.raise_for_status()
        return r.json()

    def gql(self, query: str, variables: dict) -> dict:
        r = self.c.post(API + "/graphql", json={"query": query, "variables": variables})
        r.raise_for_status()
        j = r.json()
        if j.get("errors"):
            raise RuntimeError("; ".join(e.get("message", "?")[:160] for e in j["errors"]))
        return j["data"]["viewer"]["zones"][0]


def _groups(cf: CF, zone: str, since, until, dims: str, extra_filter: str = "", limit: int = 5000) -> list:
    q = ("query($z:String!,$s:Time!,$u:Time!){viewer{zones(filter:{zoneTag:$z}){"
         f"r:httpRequestsAdaptiveGroups(limit:{limit},filter:{{datetime_geq:$s,datetime_lt:$u,"
         f"userAgent_notlike:\"{OWN}\"{extra_filter}}},orderBy:[count_DESC])"
         f"{{count dimensions{{{dims}}}}}}}}}}}")
    return cf.gql(q, {"z": zone, "s": iso(since), "u": iso(until)})["r"]


def _firewall(cf: CF, zone: str, since, until) -> list:
    q = ("query($z:String!,$s:Time!,$u:Time!){viewer{zones(filter:{zoneTag:$z}){"
         "f:firewallEventsAdaptive(limit:10000,filter:{datetime_geq:$s,datetime_lt:$u},orderBy:[datetime_DESC])"
         "{action source ruleId clientRequestHTTPHost clientRequestPath clientCountryName clientAsn "
         "clientASNDescription userAgent datetime}}}}")
    return cf.gql(q, {"z": zone, "s": iso(since), "u": iso(until)})["f"]


def tunnels(cf: CF, account: str) -> list[dict]:
    """Every tunnel on the account with its public hostnames, so a hostname
    published outside the cluster's tunnels shows up in the report."""
    out = []
    for t in cf.rest(f"/accounts/{account}/cfd_tunnel?is_deleted=false&per_page=100").get("result", []):
        hosts = []
        try:
            cfg = cf.rest(f"/accounts/{account}/cfd_tunnel/{t['id']}/configurations").get("result") or {}
            for rule in (cfg.get("config") or {}).get("ingress", []):
                if rule.get("hostname"):
                    hosts.append({"hostname": rule["hostname"], "path": rule.get("path"), "service": rule.get("service")})
        except httpx.HTTPError:
            pass
        conns = t.get("connections") or []
        out.append({"name": t.get("name"), "id": t["id"][:8], "status": t.get("status"),
                    "connector_versions": sorted({c.get("client_version") for c in conns}),
                    "origin_ips": sorted({c.get("origin_ip") for c in conns}), "ingress": hosts})
    return out


def run(since: dt.datetime, until: dt.datetime) -> dict:
    env = read_env(CF_ENV)
    token = env.get("CLOUDFLARE_READ_TOKEN")
    if not token:
        return {"status": "skipped", "reason": f"{CF_ENV} ontbreekt (CLOUDFLARE_READ_TOKEN)"}
    cf = CF(token)
    zones = cf.rest(f"/zones?name={CF_ZONE}")["result"]
    if not zones:
        return {"status": "error", "reason": f"zone {CF_ZONE} niet zichtbaar voor het token"}
    zone, account = zones[0]["id"], zones[0]["account"]["id"]
    out: dict = {"status": "ok", "zone": CF_ZONE, "plan": zones[0]["plan"]["name"], "sampled": True}

    per_host: dict[str, dict] = defaultdict(lambda: {"requests": 0, "status": Counter()})
    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost edgeResponseStatus"):
        h = g["dimensions"]["clientRequestHTTPHost"].split(":")[0]
        per_host[h]["requests"] += g["count"]
        per_host[h]["status"][f"{g['dimensions']['edgeResponseStatus'] // 100}xx"] += g["count"]

    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost clientRequestPath",
                     ",edgeResponseStatus_in:[404,410]", limit=2000):
        h = g["dimensions"]["clientRequestHTTPHost"].split(":")[0]
        per_host[h].setdefault("not_found", Counter())[g["dimensions"]["clientRequestPath"][:120]] += g["count"]

    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost clientRequestPath edgeResponseStatus", limit=5000):
        p = g["dimensions"]["clientRequestPath"]
        if SCANNER_PATHS.search(p):
            h = g["dimensions"]["clientRequestHTTPHost"].split(":")[0]
            per_host[h].setdefault("scanner_paths", Counter())[f"{g['dimensions']['edgeResponseStatus']} {p[:100]}"] += g["count"]

    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost userAgent", limit=3000):
        h = g["dimensions"]["clientRequestHTTPHost"].split(":")[0]
        cat, name = classify_ua(g["dimensions"]["userAgent"])
        per_host[h].setdefault("ua", Counter())[(cat, name)] += g["count"]
        per_host[h].setdefault("ua_categories", Counter())[cat] += g["count"]

    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost clientCountryName", limit=3000):
        h = g["dimensions"]["clientRequestHTTPHost"].split(":")[0]
        per_host[h].setdefault("countries", Counter())[g["dimensions"]["clientCountryName"]] += g["count"]

    ips_per_host: dict[str, Counter] = defaultdict(Counter)
    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost clientIP", limit=5000):
        ips_per_host[g["dimensions"]["clientRequestHTTPHost"].split(":")[0]][g["dimensions"]["clientIP"]] += g["count"]

    for g in _groups(cf, zone, since, until, "clientRequestHTTPHost verifiedBotCategory", limit=500):
        cat = g["dimensions"]["verifiedBotCategory"]
        if cat:
            h = g["dimensions"]["clientRequestHTTPHost"].split(":")[0]
            per_host[h].setdefault("verified_bots", Counter())[cat] += g["count"]

    hosts = {}
    for h, d in sorted(per_host.items(), key=lambda kv: -kv[1]["requests"]):
        asn, _ = geo.aggregate(ips_per_host.get(h, Counter()))
        hosts[h] = {
            "requests": d["requests"], "status": dict(sorted(d["status"].items())),
            "top_not_found": d.get("not_found", Counter()).most_common(15),
            "scanner_paths": d.get("scanner_paths", Counter()).most_common(15),
            "ua_categories": d.get("ua_categories", Counter()).most_common(),
            "top_user_agents": [[c, n, k] for (c, n), k in d.get("ua", Counter()).most_common(15)],
            "top_countries": d.get("countries", Counter()).most_common(10),
            "top_asn": asn[:10],
            "verified_bots": d.get("verified_bots", Counter()).most_common(),
        }
    out["hosts"] = hosts

    try:
        fw = _firewall(cf, zone, since, until)
        fw = [e for e in fw if "westerweel-selfscan" not in (e.get("userAgent") or "")]
        out["security_events"] = {
            "total": len(fw),
            "by_action": Counter(e["action"] for e in fw).most_common(),
            "by_source": Counter(e["source"] for e in fw).most_common(),
            "by_host": Counter(e["clientRequestHTTPHost"] for e in fw).most_common(),
            "top_paths": Counter(f"{e['clientRequestHTTPHost']}{e['clientRequestPath'][:80]}" for e in fw).most_common(10),
            "top_asn": Counter(f"AS{e['clientAsn']} {e['clientASNDescription']}" for e in fw).most_common(10),
            "top_countries": Counter(e["clientCountryName"] for e in fw).most_common(10),
        }
    except (RuntimeError, httpx.HTTPError) as e:
        out["security_events"] = {"error": str(e)[:200]}

    try:
        out["tunnels"] = tunnels(cf, account)
    except httpx.HTTPError as e:
        out["tunnels"] = {"error": f"{e}"[:200]}
    return out
