"""The weekly HTML, in Dutch: facts first, then gaps with where they were
found, then numbered questions. Self-contained (it goes out by mail): no
external CSS, fonts or scripts."""
from __future__ import annotations

from html import escape as e

CSS = """
body{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#1d2125;background:#fff;max-width:980px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px;border-bottom:1px solid #d0d4d9;padding-bottom:4px}
h3{font-size:15px;margin:18px 0 6px}.meta{color:#5b636b;font-size:13px}
table{border-collapse:collapse;width:100%;margin:6px 0 12px;font-size:13px}
th,td{border:1px solid #d0d4d9;padding:4px 6px;text-align:left;vertical-align:top}th{background:#f2f4f6}
code,pre{font:12px/1.4 ui-monospace,Menlo,monospace}pre{background:#f6f8fa;padding:8px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.sev{display:inline-block;padding:0 6px;border-radius:3px;font-size:12px;font-weight:600;color:#fff}
.critical{background:#8b0000}.high{background:#c0392b}.medium{background:#d68910}.low{background:#5d6d7e}.info{background:#95a5a6}
.held{color:#1e7e34;font-weight:600}.broken{color:#c0392b;font-weight:700}.exposed{color:#b7791f;font-weight:600}.skipped{color:#5b636b}
.private{border-left:3px solid #c0392b;padding-left:8px}
"""


def _t(rows, head) -> str:
    if not rows:
        return "<p class=meta>geen</p>"
    h = "".join(f"<th>{e(str(x))}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def _pairs(lst, n=10) -> str:
    return ", ".join(f"{e(str(k))} ({v})" for k, v in (lst or [])[:n]) or "–"


def _traffic_block(name: str, t: dict) -> str:
    out = [f"<h3>{e(name)}</h3><p class=meta>Bron: {e(str(t.get('source', 'Cloudflare')))}"]
    if t.get("days_covered") is not None:
        out.append(f" · dagen: {len(t['days_covered'])}")
    if t.get("own_requests_excluded"):
        out.append(f" · {t['own_requests_excluded']} eigen scanverzoeken weggelaten")
    out.append("</p>")
    if "requests" in t:
        rows = [["verzoeken", t.get("requests", 0)], ["per statusklasse", _pairs(sorted((t.get("status") or {}).items()))],
                ["soort bezoeker", _pairs(t.get("ua_categories"))],
                ["landen", _pairs(t.get("top_countries"))], ["ASN's", _pairs(t.get("top_asn"), 6)]]
        if t.get("verified_bots") is not None:
            rows.append(["verified bots (Cloudflare)", _pairs(t.get("verified_bots"))])
        out.append(_t(rows, ["", ""]))
    if t.get("top_not_found"):
        out.append("<p><b>Paden die niet bestaan (404/410)</b></p>" + _t(t["top_not_found"][:10], ["pad", "aantal"]))
    if t.get("scanner_paths"):
        out.append("<p><b>Scannerpatronen</b> (wp-*, .env, .git, …)</p>" + _t(t["scanner_paths"][:10], ["pad", "aantal"]))
    if t.get("scanner_paths_2xx"):
        out.append("<p class=broken>Scannerpaden met een 2xx-antwoord:</p><pre>" + e("\n".join(t["scanner_paths_2xx"])) + "</pre>")
    if t.get("top_user_agents"):
        out.append("<p><b>User-agents</b></p>" + _t(t["top_user_agents"][:12], ["soort", "naam", "aantal"]))
    if "authenticated_users" in t:
        out.append(f"<p><b>Langs de login:</b> ingelogde verzoeken per gebruiker: {_pairs(t['authenticated_users'])}. "
                   f"Zonder login met 2xx (buiten /health en /oauth2): {_pairs(t.get('unauth_2xx_upstream'))}</p>")
    if "api_2xx" in t:
        out.append(f"<p><b>API met 2xx</b> (de log noemt geen gebruiker; auth zit vóór of in de app): "
                   f"{_pairs(t['api_2xx'])}</p>")
    if "login_errors_by_realm" in t:
        out.append(_t([["mislukte logins per realm", _pairs(t["login_errors_by_realm"])],
                       ["per fout", _pairs(t["login_errors_by_error"])], ["per client", _pairs(t["login_errors_by_client"])],
                       ["gebruikersnamen", _pairs(t["usernames_tried"])],
                       ["IP's (onbetrouwbaar, zie kc-xff-trust)", _pairs(t["top_ips"], 6)]], ["", ""]))
    return "".join(out)


def html(rep: dict) -> str:
    m = rep["meta"]
    p = [f"<!doctype html><html lang=nl><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
         f"<title>Beveiligingsrapport {e(m['week'])}</title><style>{CSS}</style></head><body>",
         f"<h1>Beveiligingsrapport {e(m['week'])}</h1>",
         f"<p class=meta>Periode {e(m['since'])} – {e(m['until'])} (UTC) · gemaakt {e(m['generated'])} · "
         f"laag 1 {e(m['layer1'])} · laag 2 {e(m['layer2'])} · Cloudflare {e(rep['cloudflare'].get('status', '?'))}. "
         "Privé: bevat reproductiestappen voor open lekken.</p>"]

    f = rep["findings"]
    p.append("<h2>1. Feiten</h2><h3>Bevindingen</h3>")
    if not f:
        p.append("<p>Geen bevindingen met een reproduceerbaar pad deze week.</p>")
    for i, x in enumerate(f, 1):
        issue = f" · issue: <a href='{e(x['issue'])}'>{e(x['issue'])}</a>" if x.get("issue") else ""
        p.append(f"<p><span class='sev {e(x['severity'])}'>{e(x['severity'])}</span> <b>F{i}. {e(x['title'])}</b> "
                 f"({e(x['site'])}, {e(x['source'])}){issue}<br>{e(x['summary'])}<br>"
                 f"<span class=meta>Vindplaats: {e(x['where'] or x['site'])}</span></p>")
        if x.get("private"):
            p.append("<div class=private><pre>" + e("\n".join(x["private"])) + "</pre></div>")

    p.append("<h3>Laag 2: actieve controles (niet-destructief)</h3>")
    p.append(_t([[c["id"], c["site"], c["title"], c["result"], c["summary"]] for c in rep["layer2"]],
                ["controle", "site", "wat", "uitkomst", "toelichting"]).replace("<td>broken</td>", "<td class=broken>broken</td>")
             .replace("<td>held</td>", "<td class=held>held</td>").replace("<td>exposed</td>", "<td class=exposed>exposed</td>"))

    l1 = rep["layer1"]
    p.append("<h3>Laag 1: TLS</h3>")
    p.append(_t([[t.get("host"), ", ".join(t.get("protocols", [])), len(t.get("weak_tls12_ciphers", [])),
                  (t.get("cert_not_after") or "")[:10], t.get("chain_trusted"), t.get("hsts_max_age"),
                  ", ".join(t.get("vulnerabilities", [])) or "–"] for t in (l1.get("tls") or []) if "host" in t],
                ["host", "protocollen", "zwakke TLS1.2-suites", "cert tot", "keten ok", "HSTS max-age", "kwetsbaar"]))
    p.append("<h3>Laag 1: headers</h3>")
    p.append(_t([[h["site"], h.get("status", h.get("error", "")), ", ".join(h.get("missing", [])) or "–",
                  "ja" if h.get("security_txt") else "nee", "; ".join(h.get("cookies", [])) or "–", h.get("banner") or "–"]
                 for h in (l1.get("headers") or [])], ["site", "status", "ontbreekt", "security.txt", "cookies", "banner"]))
    z = l1.get("zap") or {}
    p.append(f"<h3>Laag 1: ZAP baseline (passief)</h3><p class=meta>{e(z.get('status', ''))} {e(z.get('reason', ''))}</p>")
    for site, alerts in (z.get("sites") or {}).items():
        rows = [[a["risk"], a["alert"], a["count"], a["example"]] for a in alerts if a["risk"] != "Informational"]
        info = sum(1 for a in alerts if a["risk"] == "Informational")
        p.append(f"<p><b>{e(site)}</b> ({info} informatief weggelaten)</p>" + _t(rows, ["risico", "melding", "aantal", "voorbeeld"]))
    n = l1.get("nuclei") or {}
    p.append(f"<h3>Laag 1: nuclei (veilige tags)</h3><p class=meta>{e(str(n.get('status', '')))} "
             f"{e(n.get('reason', ''))} · {n.get('count', 0)} treffers</p>")
    nf = [x for x in n.get("findings", []) if x["severity"] != "info"]
    p.append(_t([[x["severity"], x["template"], x["name"], x["matched"]] for x in nf], ["ernst", "template", "naam", "url"]))
    ninfo = [x for x in n.get("findings", []) if x["severity"] == "info"]
    if ninfo:
        p.append(f"<p class=meta>{len(ninfo)} info-treffers: " + e(", ".join(sorted({x['template'] for x in ninfo}))[:800]) + "</p>")

    p.append("<h3>Botverkeer per site: Cloudflare (rand)</h3>")
    cf = rep["cloudflare"]
    if cf.get("status") == "ok":
        p.append("<p class=meta>Gesampelde schattingen van Cloudflare (Free plan). Eigen scanverkeer weggefilterd op user-agent.</p>")
        for host, t in cf.get("hosts", {}).items():
            p.append(_traffic_block(host, {**t, "source": "Cloudflare httpRequestsAdaptiveGroups"}))
        se = cf.get("security_events") or {}
        if "total" in se:
            p.append("<h3>Cloudflare Security Events</h3>" + _t(
                [["totaal", se["total"]], ["actie", _pairs(se["by_action"])], ["bron", _pairs(se["by_source"])],
                 ["host", _pairs(se["by_host"])], ["paden", _pairs(se["top_paths"])], ["ASN's", _pairs(se["top_asn"], 6)],
                 ["landen", _pairs(se["top_countries"])]], ["", ""]))
        if isinstance(cf.get("tunnels"), list):
            p.append("<h3>Tunnels op het account</h3>" + _t(
                [[t["name"], t["status"], ", ".join(t["connector_versions"]), ", ".join(t["origin_ips"]),
                  "; ".join(f"{i['hostname']}{' ' + i['path'] if i.get('path') else ''} → {i['service']}" for i in t["ingress"])]
                 for t in cf["tunnels"]], ["tunnel", "status", "cloudflared", "origin-IP", "publieke ingress"]))
    else:
        p.append(f"<p class=meta>Overgeslagen: {e(cf.get('reason', ''))}</p>")

    p.append("<h3>Botverkeer per site: origin-logs</h3>")
    for site, t in rep["traffic"].items():
        p.append(_traffic_block(site, t))

    p.append("<h2>2. Gaten</h2>")
    p.append(_t([[i, g["what"], g["where"], g.get("why", "")] for i, g in enumerate(rep["gaps"], 1)],
                ["#", "gat", "vindplaats", "noot"]))

    p.append("<h2>3. Vragen</h2>")
    if rep["questions"]:
        p.append("<ol>" + "".join(f"<li>{e(q)}</li>" for q in rep["questions"]) + "</ol>")
    else:
        p.append("<p>Geen.</p>")
    p.append("<p class=meta>IP→ASN/land: DB-IP Lite (CC BY 4.0), lokaal opgezocht. "
             "Gemaakt door homelab tools/security-report.</p></body></html>")
    return "".join(p)
