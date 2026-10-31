# Count-only S3 probe, run inside wordsworth-api with the app's own S3 settings
# (env): python s3probe.py [one|redacted|all]. It checks the real identity and the S3 auth path. Prints counts,
# byte totals and a pass/fail per check; never object content or credentials.
import hashlib, os, sys, boto3
s3 = boto3.client("s3", endpoint_url=os.environ["WORDSWORTH_S3_ENDPOINT_URL"],
                  region_name=os.environ.get("WORDSWORTH_S3_REGION", "us-east-1"),
                  aws_access_key_id=os.environ.get("WORDSWORTH_S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID"),
                  aws_secret_access_key=os.environ.get("WORDSWORTH_S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY"))
b = os.environ["WORDSWORTH_S3_BUCKET"]; n = 0; size = 0; red = []; allobj = []
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=b):
    for o in page.get("Contents", []):
        n += 1; size += o["Size"]; allobj.append(o)
        if o["Key"].startswith("redacted/"): red.append(o)
print(f"objects={n} bytes={size} redacted={len(red)}")
mode = sys.argv[1] if len(sys.argv) > 1 else "one"
ok = bad = 0
for o in {"all": allobj, "redacted": red}.get(mode, red[:1]):
    body = s3.get_object(Bucket=b, Key=o["Key"])["Body"].read()
    good = len(body) == o["Size"] and (hashlib.md5(body).hexdigest() == o["ETag"].strip('"') or "-" in o["ETag"])
    ok += good; bad += not good
print(f"{mode} GET ok={ok} bad={bad}")
