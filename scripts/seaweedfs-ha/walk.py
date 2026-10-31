# Walk a SeaweedFS filer over its HTTP JSON listing (read-only GETs).
# Prints path, size, md5 and the chunk list (file id@offset+size) per file
# under /buckets/wordsworth. Usage: walk.py http://filer:8888
import base64, json, sys, urllib.parse, urllib.request
base = sys.argv[1]
def ls(d):
    last = ""
    while True:
        q = urllib.parse.urlencode({"limit": 1000, "lastFileName": last})
        req = urllib.request.Request(f"{base}{urllib.parse.quote(d)}/?{q}", headers={"Accept": "application/json"})
        js = json.load(urllib.request.urlopen(req))
        ents = js.get("Entries") or []
        for e in ents:
            yield e
        if not js.get("ShouldDisplayLoadMore"):
            return
        last = js["LastFileName"]
def walk(d):
    for e in ls(d):
        p = e["FullPath"]
        if e.get("Mode", 0) & (1 << 31):
            yield from walk(p)
        else:
            md5 = base64.b64decode(e["Md5"]).hex() if e.get("Md5") else "-"
            chunks = ",".join(f"{c.get('file_id')}@{c.get('offset', 0)}+{c.get('size')}" for c in e.get("chunks") or [])
            print(f"{p}\t{e.get('FileSize', 0)}\t{md5}\t{chunks}")
for _ in walk("/buckets/wordsworth"):
    pass
