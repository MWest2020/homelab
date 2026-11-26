from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import time
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
    """Run a command on jumpy (kubectl lives there). Output is decoded with
    errors="replace": request logs carry whatever bytes bots send, and one
    non-UTF-8 byte must not lose a whole collect."""
    return run_text(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", JUMPY, cmd], input=input, timeout=timeout)


def run_text(argv: list[str], *, input: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(argv, input=input, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, stdin=None if input is not None else subprocess.DEVNULL)


SCOPE_PREFIX = "secreport-"


def capped(argv: list[str], name: str = "scan") -> list[str]:
    """Wrap a scanner in a transient systemd scope with a hard memory cap and
    no swap, so one scanner can never starve agent-lxc. Scanners run one at a
    time. The scope is named secreport-<name>-<pid> so a stopped service (or
    the next run) can stop leftovers: `systemctl --user stop 'secreport-*'`.
    Falls back to the bare command where there is no user systemd."""
    if shutil.which("systemd-run") and os.environ.get("SECREPORT_NO_SCOPE") != "1":
        return ["systemd-run", "--user", "--scope", "--quiet", "--collect",
                f"--unit={SCOPE_PREFIX}{name}-{os.getpid()}-{int(time.time())}",
                "-p", f"MemoryMax={SCANNER_MEMORY}", "-p", "MemorySwapMax=0", "--", *argv]
    return argv


def stop_scopes(name: str = "") -> None:
    """Stop leftover scanner scopes (e.g. a ZAP still holding its port after an
    aborted run). Best effort."""
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "stop", f"{SCOPE_PREFIX}{name}*.scope"],
                       capture_output=True, text=True, timeout=60)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    tmp.replace(path)
