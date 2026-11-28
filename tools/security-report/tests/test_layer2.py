import httpx

from secreport import layer2


def _session(ingest_status: int, detail: str = "caller not authorized for corpus read") -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/console/login":
            return httpx.Response(303, headers={"location": f"{layer2.WW}/console"})
        if req.url.path == "/ingest" and req.method == "POST":
            return httpx.Response(ingest_status, json={"detail": detail})
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ingest_gate_results(monkeypatch):
    monkeypatch.setattr(layer2.time, "sleep", lambda _s: None)
    assert layer2.ww_ingest_gate(_session(403)).result == "held"
    assert layer2.ww_ingest_gate(_session(422, "field required")).result == "broken"
    assert layer2.ww_ingest_gate(_session(403, "blocked by waf")).result == "exposed"
    skipped = layer2.ww_ingest_gate(None, "no session")
    assert skipped.result == "skipped" and "no session" in skipped.summary
