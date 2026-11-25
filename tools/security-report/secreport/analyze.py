"""From raw results to what Mark reads: findings (facts), gaps (with where
they were found) and numbered questions. Only `broken` layer-2 checks and
scanner hits at medium or above count as findings; the rest is context."""
from __future__ import annotations

import json
from pathlib import Path

from .config import SITES

KNOWN_ISSUES = Path(__file__).resolve().parent.parent / "known-issues.json"

SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Severity of the layer-2 checks when they break (judged once, by hand).
L2_SEVERITY = {
    "kc-admin-direct": "high",
    "ww-unauthenticated-routes": "high",
    "ww-proxy-path-bypass": "high",
    "ww-proxy-header-spoof": "high",
    "ww-reveal-without-grant": "high",
    "ww-direct-api": "high",
    "wanderer-tunnel-path-filter": "high",
    "kc-open-redirect": "medium",
    "ww-proxy-open-redirect": "medium",
    "ww-cors": "medium",
    "kc-login-rate-limit": "medium",
}

WHERE = {s.name: s.where for s in SITES} | {
    "iam": "Cloudflare tunnel 'keycloak' (remote ingress) + homelab cluster-config/infra/keycloak",
    "wordsworth": "homelab cluster-config/infra/wordsworth/oauth2-proxy.yaml + wordsworth repo",
    "wanderer": "Cloudflare tunnel 'wanderer' (remote ingress) + homelab cluster-config/infra/wanderer",
}


def _private():
    from .layer2 import load_private
    try:
        return load_private()
    except Exception:  # noqa: BLE001 - a broken private file must not kill the report
        return None


_P = _private()
if _P is not None:
    L2_SEVERITY |= getattr(_P, "SEVERITY", {})
    WHERE |= getattr(_P, "WHERE", {})


def _known() -> dict:
    try:
        return json.loads(KNOWN_ISSUES.read_text())
    except (OSError, ValueError):
        return {}


def findings(l1: dict, l2: list[dict]) -> list[dict]:
    known = _known()
    out = []
    for c in l2:
        if c.get("result") == "broken":
            out.append({"source": "laag 2", "id": c["id"], "site": c["site"], "title": c["title"],
                        "severity": L2_SEVERITY.get(c["id"], "medium"), "summary": c["summary"],
                        "private": c.get("private", []), "where": WHERE.get(c["site"], "?"),
                        "repo": c.get("repo"), "issue": known.get(c["id"])})
    for f in (l1.get("nuclei") or {}).get("findings", []):
        if SEV.get(f["severity"], 9) <= SEV["medium"]:
            fid = f"nuclei:{f['template']}@{f['host']}"
            out.append({"source": "nuclei", "id": fid, "site": f["host"], "title": f["name"],
                        "severity": f["severity"], "summary": f"{f['matched']}",
                        "private": [json.dumps(f["extracted"])] if f["extracted"] else [],
                        "where": "", "repo": None, "issue": known.get(fid)})
    for t in l1.get("tls") or []:
        if t.get("vulnerabilities") or t.get("old_protocols") or t.get("chain_trusted") is False:
            fid = f"tls:{t.get('host')}"
            out.append({"source": "TLS", "id": fid, "site": t.get("host"), "title": "TLS-configuratie",
                        "severity": "high" if t.get("vulnerabilities") or t.get("chain_trusted") is False else "medium",
                        "summary": f"oude protocollen {t.get('old_protocols')}, kwetsbaarheden {t.get('vulnerabilities')}, "
                                   f"keten vertrouwd {t.get('chain_trusted')}",
                        "private": [], "where": "", "repo": None, "issue": known.get(fid)})
    if _P is not None:
        # Findings that were reported directly and are deliberately no longer probed.
        out += [dict(n) for n in getattr(_P, "NOTES", [])]
    out.sort(key=lambda f: SEV.get(f["severity"], 9))
    return out


def gaps(l1: dict, l2: list[dict], traffic: dict, cf: dict) -> list[dict]:
    g: list[dict] = []

    def add(what, where, why=""):
        g.append({"what": what, "where": where, "why": why})

    for c in l2:
        if c.get("result") == "exposed":
            add(f"{c['title']}: {c['summary']}", WHERE.get(c["site"], c["site"]))
        if c.get("result") == "skipped":
            add(f"Niet getest: {c['title']}. {c['summary']}", WHERE.get(c["site"], c["site"]))
    for h in l1.get("headers") or []:
        if h.get("missing"):
            add(f"{h['site']}: ontbrekende headers {', '.join(h['missing'])}", WHERE.get(h["site"], h["url"]))
        if h.get("exposed_files"):
            add(f"{h['site']}: bestanden die niet publiek horen: {', '.join(h['exposed_files'])}", WHERE.get(h["site"], h["url"]))
        if h.get("cookies"):
            add(f"{h['site']}: cookie-vlaggen {'; '.join(h['cookies'])}", WHERE.get(h["site"], h["url"]))
        if h.get("banner"):
            add(f"{h['site']}: versie-/serverbanner {h['banner']}", WHERE.get(h["site"], h["url"]))
    weak: dict[tuple, list[str]] = {}
    for t in l1.get("tls") or []:
        if t.get("weak_tls12_ciphers"):
            weak.setdefault(tuple(t["weak_tls12_ciphers"]), []).append(t["host"])
        if t.get("error"):
            add(f"{t['host']}: TLS-scan mislukt ({t['error']})", t["host"])
    for suites, hosts in weak.items():
        add(f"TLS 1.2 accepteert {len(suites)} zwakkere suites (CBC of zonder forward secrecy, bv. {suites[0]}) op "
            f"{', '.join(hosts)}", "Cloudflare edge-instellingen (SSL/TLS → Edge Certificates)" if all(
                h.endswith("westerweel.work") for h in hosts) else ", ".join(hosts),
            "op Cloudflare is de cipher-lijst een zone-instelling, niet iets van de origin")
    zap = (l1.get("zap") or {}).get("sites") or {}
    for site, alerts in zap.items():
        mid = [a for a in alerts if a["risk"] in ("High", "Medium")]
        if mid:
            add(f"{site}: ZAP passief {len(mid)}× medium/high: " + "; ".join(f"{a['alert']} ({a['count']})" for a in mid[:4]),
                WHERE.get(site, site))
    for f in (l1.get("funnel_dns") or []):
        if f.get("public_dns"):
            add(f"{f['host']} staat nu in publieke DNS ({f['public_dns']}): Funnel is publiek, toevoegen aan de scope",
                "Tailscale Funnel-annotatie in homelab cluster-config")
    for site, t in traffic.items():
        if site.endswith("-events"):
            continue
        if not t.get("has_ip"):
            add(f"{site}: de log bevat geen client-IP, dus geen ASN/land uit de origin", t["source"])
        if not t.get("has_ua"):
            add(f"{site}: de log bevat geen user-agent", t["source"])
        if len(t.get("days_covered", [])) < 7:
            add(f"{site}: maar {len(t.get('days_covered', []))} van 7 dagen in de cache", t["source"],
                "de collector draait elke 3 uur; volle weken vanaf de tweede run")
    if cf.get("status") != "ok":
        add(f"Cloudflare-analytics: {cf.get('status')} ({cf.get('reason', '')})", "~/.config/cloudflare/read.env")
    else:
        if "error" in (cf.get("security_events") or {}):
            add(f"Cloudflare Security Events: {cf['security_events']['error']}", "GraphQL firewallEventsAdaptive")
        hosts_in_scope = {s.url.split('/')[2] for s in SITES}
        for t in cf.get("tunnels") or []:
            for i in t.get("ingress", []):
                if i["hostname"] not in hosts_in_scope:
                    add(f"Tunnel '{t['name']}' publiceert {i['hostname']}, dat niet in de scope van dit rapport staat",
                        "Cloudflare Zero Trust → Tunnels")
    return g


def questions(l2: list[dict], cf: dict) -> list[str]:
    q = []
    ids = {c["id"]: c for c in l2}
    if ids.get("ww-idor-documents", {}).get("result") == "skipped":
        q.append("Mag ik in realm westerweel één testgebruiker aanmaken (selfscan@westerweel.work, geen rollen, "
                 "niet in de label-lijsten) om IDOR en reveal-zonder-grant met een echte sessie te testen? "
                 "Default: niet aanmaken; die twee blijven ongetest.")
    if _P is not None and hasattr(_P, "questions"):
        q += _P.questions(l2)
    if cf.get("status") != "ok":
        q.append("Wil je een read-only Cloudflare-token in ~/.config/cloudflare/read.env zetten? Default: dat deel blijft leeg.")
    return q
