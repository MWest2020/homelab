"""IP → ASN / country, locally. DB-IP Lite (CC BY 4.0, https://db-ip.com),
fetched once a month into TOOLS/geo. Visitor IPs never leave this host: no
lookup service is asked."""
from __future__ import annotations

import datetime as dt
import gzip
from collections import Counter
from functools import lru_cache

import httpx
import maxminddb

from .config import TOOLS, USER_AGENT

GEO = TOOLS / "geo"


def _ensure(kind: str) -> maxminddb.Reader | None:
    GEO.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    months = [today.strftime("%Y-%m"), (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")]
    for m in months:
        f = GEO / f"dbip-{kind}-lite-{m}.mmdb"
        if f.exists():
            return maxminddb.open_database(str(f))
    for m in months:
        f = GEO / f"dbip-{kind}-lite-{m}.mmdb"
        try:
            r = httpx.get(f"https://download.db-ip.com/free/dbip-{kind}-lite-{m}.mmdb.gz",
                          headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True)
            if r.status_code == 200:
                f.write_bytes(gzip.decompress(r.content))
                for old in GEO.glob(f"dbip-{kind}-lite-*.mmdb"):
                    if old != f:
                        old.unlink()
                return maxminddb.open_database(str(f))
        except (httpx.HTTPError, OSError):
            continue
    return None


@lru_cache(maxsize=2)
def reader(kind: str):
    return _ensure(kind)


def lookup(ip: str) -> tuple[str, str]:
    asn = country = "?"
    try:
        ra, rc = reader("asn"), reader("country")
        if ra:
            a = ra.get(ip) or {}
            if a:
                asn = f"AS{a.get('autonomous_system_number', '?')} {a.get('autonomous_system_organization', '')}".strip()
        if rc:
            c = rc.get(ip) or {}
            country = (c.get("country") or {}).get("iso_code", "?")
    except ValueError:
        pass
    return asn, country


def aggregate(ips: Counter) -> tuple[list, list]:
    asn, country = Counter(), Counter()
    for ip, n in ips.items():
        a, c = lookup(ip)
        asn[a] += n
        country[c] += n
    return asn.most_common(), country.most_common()
