from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx

from .config import JUMPY, SCANNER_MEMORY, USER_AGENT


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def client(**kw) -> httpx.Client:
    kw.setdefault("timeout", 20)
    kw.setdefault("follow_redirects", False)
    headers = {"User-Agent": USER_AGENT, **kw.pop("headers", {})}
    return httpx.Client(headers=headers, **kw)


def read_env(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; quotes stripped. Values are never logged."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return out


def jumpy(cmd: str, *, input: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command on jumpy (kubectl lives there)."""
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", JUMPY, cmd],
                          input=input, capture_output=True, text=True, timeout=timeout)


def capped(argv: list[str]) -> list[str]:
    """Wrap a scanner in a transient systemd scope with a hard memory cap and
    no swap, so one scanner can never starve agent-lxc. Scanners run one at a
    time. Falls back to the bare command where there is no user systemd."""
    if shutil.which("systemd-run") and os.environ.get("SECREPORT_NO_SCOPE") != "1":
        return ["systemd-run", "--user", "--scope", "--quiet",
                "-p", f"MemoryMax={SCANNER_MEMORY}", "-p", "MemorySwapMax=0", "--", *argv]
    return argv


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    tmp.replace(path)
