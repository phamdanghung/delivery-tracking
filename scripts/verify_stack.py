"""Verify live M0 dependencies; remove only the unique object created by this run."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import boto3
import httpx
from redis import Redis

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import Settings  # noqa: E402 -- add the workspace API to the import path first

settings = Settings(_env_file=root / ".env")
checks: dict[str, object] = {}
with httpx.Client(timeout=20, trust_env=False) as client:
    live = client.get("http://127.0.0.1:8000/health/live")
    live.raise_for_status()
    assert live.json() == {"status": "ok"}
    UUID(live.headers["x-request-id"])
    checks["api_live"] = live.status_code
    ready = client.get("http://127.0.0.1:8000/health/ready")
    ready.raise_for_status()
    assert all(ready.json()["checks"].values())
    assert set(ready.json()["checks"]) == {"database", "redis", "storage", "traccar"}
    checks["api_ready"] = ready.json()
    web = client.get("http://127.0.0.1:3000/")
    web.raise_for_status()
    assert 'lang="vi"' in web.text
    checks["admin_web"] = web.status_code
    traccar = client.get(settings.traccar_url.rstrip("/") + "/api/server")
    traccar.raise_for_status()
    checks["traccar_server"] = traccar.status_code
    redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=5)
    assert redis.ping()
    redis.close()
    checks["redis_ping"] = "PONG"
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
    )
    s3.head_bucket(Bucket=settings.s3_bucket)
    assert s3.get_bucket_versioning(Bucket=settings.s3_bucket)["Status"] == "Enabled"
    key = "m0-verification/" + uuid4().hex
    version = None
    try:
        result = s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=b"M0 real storage check")
        version = result["VersionId"]
        response = s3.get_object(Bucket=settings.s3_bucket, Key=key, VersionId=version)
        stream = response["Body"]
        assert stream.read() == b"M0 real storage check"
        stream.close()
        anonymous = client.get(f"{settings.s3_endpoint_url}/{settings.s3_bucket}/{key}")
        assert anonymous.status_code == 403
        checks["minio"] = {
            "bucket": settings.s3_bucket,
            "versioning": "Enabled",
            "signed_write_read": "PASS",
            "anonymous_read": anonymous.status_code,
        }
    finally:
        if version is not None:
            s3.delete_object(Bucket=settings.s3_bucket, Key=key, VersionId=version)
        s3.close()

report = {
    "verified_at": datetime.now(UTC).isoformat(),
    "checks": checks,
    "result": "PASS",
}
output = root / "artifacts/m0-stack-health.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
