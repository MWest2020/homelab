import datetime as dt
import json

from secreport import analyze, config, logs, util


def test_non_utf8_output_does_not_crash():
    r = util.run_text(["printf", "GET /x \\300\\377 HTTP/1.1\\n"])
    assert r.returncode == 0 and "�" in r.stdout


def test_k8s_sources_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "CACHE", tmp_path / "logs")
    good = ('[pod/wordsworth-auth-1/oauth2-proxy] 2026-11-25T14:43:21.0Z 10.0.0.1:1 - r - - [2026/11/25 14:43:21] '
            'wordsworth.westerweel.work GET - "/x�" HTTP/1.1 "bot" 404 2 0.000')

    def fake_jumpy(cmd, **kw):
        if "-n wordsworth" in cmd:
            return util.subprocess.CompletedProcess([], 0, good + "\n", "")
        raise UnicodeDecodeError("utf-8", b"\xc0", 0, 1, "invalid start byte")

    monkeypatch.setattr(logs, "jumpy", fake_jumpy)
    out = logs.collect_k8s()
    assert out["wordsworth"] == 1
    assert all(str(v).startswith("error") for k, v in out.items() if k != "wordsworth")


def test_plesk_backoff():
    now = 1_000_000.0
    assert logs.plesk_due({"last_attempt": 0, "failures": 0}, now)[0]
    assert not logs.plesk_due({"last_attempt": now - 3600, "failures": 0}, now)[0]          # < 20 h: wait
    assert logs.plesk_due({"last_attempt": now - 21 * 3600, "failures": 2}, now)[0]
    due, why = logs.plesk_due({"last_attempt": 0, "failures": config.PLESK_MAX_FAILURES, "last_error": "x"}, now)
    assert not due and "plesk-reset" in why


def test_prune(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "CACHE", tmp_path / "logs")
    monkeypatch.setattr(logs, "STATE", tmp_path)
    today = dt.date(2026, 11, 26)
    (tmp_path / "logs/x").mkdir(parents=True)
    old, fresh = today - dt.timedelta(days=40), today - dt.timedelta(days=3)
    for d in (old, fresh):
        (tmp_path / f"logs/x/{d}.log").write_text("a\n")
    (tmp_path / f"{today - dt.timedelta(weeks=27)}.html").write_text("x")
    (tmp_path / f"{today - dt.timedelta(weeks=2)}.json").write_text("{}")
    gone = logs.prune(today)
    assert gone == {"cache": 1, "reports": 1}
    assert (tmp_path / f"logs/x/{fresh}.log").exists()


def test_plesk_sites_stay_light():
    plesk = [s for s in config.SITES if s.kind == "plesk"]
    assert plesk and all(s.deep is False and s.tls_light is True for s in plesk)


def test_excluded_hosts_never_scanned():
    hosts = {s.url.split("/")[2] for s in config.SITES}
    assert "billbird.westerweel.work" in config.EXCLUDED_HOSTS
    assert not hosts & config.EXCLUDED_HOSTS


def test_excluded_hosts_not_a_gap():
    cf = {"status": "ok", "tunnels": [{"name": "billbird.westerweel.work", "ingress": [
        {"hostname": "billbird.westerweel.work", "path": None, "service": "http://localhost:8080"}]}]}
    gaps = analyze.gaps({}, [], {}, cf)
    assert not any("billbird" in g["what"] for g in gaps)
