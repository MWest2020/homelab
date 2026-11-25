"""secreport collect | report [--skip ...]

collect: pull request lines into the cache (every 3 hours, timer).
report:  the weekly run: Cloudflare + logs over the last 7 days, layer 1,
         layer 2, then <date>.html + <date>.json in ~/.local/state/security-report.
         The coding session mails the HTML; this tool never sends mail.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from . import analyze, cloudflare, layer1, layer2, logs, render
from .config import STATE
from .util import iso, now, write_json


def _record_window(start: dt.datetime, end: dt.datetime) -> None:
    f = STATE / "selfscan-windows.json"
    wins = json.loads(f.read_text()) if f.exists() else []
    wins.append([start.isoformat(), end.isoformat()])
    cutoff = (now() - dt.timedelta(days=40)).isoformat()
    write_json(f, [w for w in wins if w[1] >= cutoff])


def report(skip: set[str], days: int) -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    until = now()
    since = until - dt.timedelta(days=days)

    print("collect …", file=sys.stderr)
    collected = logs.collect()
    print("cloudflare …", file=sys.stderr)
    try:
        cf = cloudflare.run(since, until) if "cloudflare" not in skip else {"status": "skipped", "reason": "uitgezet"}
    except Exception as e:  # noqa: BLE001
        cf = {"status": "error", "reason": f"{type(e).__name__}: {e}"[:300]}
    print("traffic …", file=sys.stderr)
    traffic = logs.summarize(since, until)

    scan_start = now()
    l1 = layer1.run(skip) if "layer1" not in skip else {}
    print("layer2 …", file=sys.stderr)
    l2 = layer2.run() if "layer2" not in skip else []
    _record_window(scan_start - dt.timedelta(minutes=1), now() + dt.timedelta(minutes=2))

    rep = {
        "meta": {"week": f"{until.isocalendar().year}-W{until.isocalendar().week:02d}",
                 "since": iso(since), "until": iso(until), "generated": iso(now()),
                 "layer1": "overgeslagen" if "layer1" in skip else "gedraaid",
                 "layer2": "overgeslagen" if "layer2" in skip else "gedraaid", "collect": collected},
        "cloudflare": cf, "traffic": traffic, "layer1": l1, "layer2": l2,
    }
    rep["findings"] = analyze.findings(l1, l2)
    rep["gaps"] = analyze.gaps(l1, l2, traffic, cf)
    rep["questions"] = analyze.questions(l2, cf)

    stamp = until.date().isoformat()
    write_json(STATE / f"{stamp}.json", rep)
    (STATE / f"{stamp}.html").write_text(render.html(rep))
    (STATE / "latest.html").unlink(missing_ok=True)
    (STATE / "latest.html").symlink_to(f"{stamp}.html")
    print(STATE / f"{stamp}.html")
    print(f"findings: {len(rep['findings'])}, gaps: {len(rep['gaps'])}, questions: {len(rep['questions'])}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="secreport")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect")
    r = sub.add_parser("report")
    r.add_argument("--skip", default="", help="comma list: layer1,layer2,cloudflare,headers,tls,zap,nuclei,funnel_dns")
    r.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    if a.cmd == "collect":
        print(json.dumps(logs.collect()))
        return 0
    return report({s for s in a.skip.split(",") if s}, a.days)


if __name__ == "__main__":
    sys.exit(main())
