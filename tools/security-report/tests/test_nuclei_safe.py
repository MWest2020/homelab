"""Runs `nuclei -tl` with exactly the arguments a scan uses and fails if any
selected template could change state or talk to a third party."""
import subprocess
from pathlib import Path

import pytest

from secreport import layer1
from secreport.config import TOOLS

BINARY, TEMPLATES = TOOLS / "bin/nuclei", TOOLS / "nuclei-templates"
pytestmark = pytest.mark.skipif(not BINARY.exists() or not TEMPLATES.exists(),
                                reason="nuclei not installed (install-scanners.sh)")


def test_selected_templates_are_safe(tmp_path):
    sel = layer1.select_templates(BINARY, TEMPLATES, tmp_path)
    assert len(sel["http"]) + len(sel["ssl"]) > 100
    loaded = []
    # What the scan would actually load, per run (the ssl run keeps protocol tcp):
    for name in ("http", "ssl"):
        lst = tmp_path / f"list-{name}.txt"
        lst.write_text("\n".join(map(str, sel[name])) + "\n")
        p = subprocess.run([str(BINARY), "-duc", "-silent", "-nc", "-tl", "-t", str(lst),
                            *layer1.nuclei_filter_args(TEMPLATES, ssl=(name == "ssl"))],
                           capture_output=True, text=True, timeout=600,
                           env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}, stdin=subprocess.DEVNULL)
        loaded += [ln.strip() for ln in p.stdout.splitlines() if ln.strip().endswith((".yaml", ".yml"))]
    # the ssl run never loads anything outside ssl/
    assert all("/ssl/" in str(t) for t in sel["ssl"])
    assert loaded, p.stderr[-300:]
    bad = []
    for t in loaded:
        why = layer1.unsafe_reason(Path(t))
        if why or any(f"/{d}/" in t for d in layer1.NUCLEI_EXCLUDE_DIRS):
            bad.append((t, why or "excluded dir"))
    assert not bad, bad[:10]
    names = {Path(t).stem for t in loaded}
    for known_bad in ("nacos-create-user", "symantec-phishing-panel"):
        assert known_bad not in names
    # coverage must not vanish silently: the core GET-only exposure checks stay selected
    for known_good in ("git-config", "deprecated-tls"):
        assert known_good in names, f"{known_good} no longer selected"
