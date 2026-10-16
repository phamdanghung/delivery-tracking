"""Read-only verification INSIDE the fresh private restore-drill network."""

import hashlib
import json
import os
import sys
import time
from urllib.parse import quote

import boto3
import httpx
from botocore.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

STAGE = "IMPORTS"


def verify() -> dict:
    global STAGE
    STAGE = "DATABASE"
    expected = json.load(open("/manifest.json"))
    engine = create_engine(
        URL.create(
            "postgresql+psycopg",
            username=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["RESTORE_PG"],
            database=os.environ["POSTGRES_DB"],
        ),
        connect_args={"connect_timeout": 10},
    )
    assets = []
    try:
        with engine.connect() as db:
            db.execute(text("SET TIME ZONE 'UTC'"))
            actual_tables = inspect(db).get_table_names()
            assert set(actual_tables) == set(expected["tables"]), "Restored table set differs"
            for name in actual_tables:
                quoted = db.dialect.identifier_preparer.quote(name)
                rows = db.execute(
                    text(f"SELECT to_jsonb(t)::text FROM {quoted} t ORDER BY 1")
                ).scalars()
                digest, count = hashlib.sha256(), 0
                for row in rows:
                    digest.update(row.encode() + b"\n")
                    count += 1
                assert {"rows": count, "sha256": digest.hexdigest()} == expected["tables"][name], (
                    "Restored table fingerprint differs"
                )
            head = db.scalar(text("SELECT version_num FROM alembic_version"))
            assert head == expected["migration_head"]
            assert db.scalar(text("SELECT PostGIS_Version()"))
            for name in ("pod_photos", "expense_receipts", "vehicle_receipts"):
                STAGE = "ASSET_METADATA"
                assets.extend(
                    db.execute(text(f"SELECT object_key,object_version,sha256 FROM {name}"))
                    .mappings()
                    .all()
                )
    finally:
        engine.dispose()
    client = boto3.client(
        "s3",
        endpoint_url="http://" + os.environ["RESTORE_MINIO"] + ":9000",
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        config=Config(connect_timeout=3, read_timeout=10, retries={"max_attempts": 0}),
    )
    bucket = os.environ["RESTORE_BUCKET"]
    STAGE = "STORAGE_READY"
    deadline = time.monotonic() + 90
    while True:
        try:
            client.head_bucket(Bucket=bucket)
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise RuntimeError("Restored private storage did not become ready") from None
            time.sleep(1)
    try:
        STAGE = "STORAGE_PRIVATE_VERSIONING"
        assert client.get_bucket_versioning(Bucket=bucket)["Status"] == "Enabled"
        with httpx.Client(timeout=10, trust_env=False) as web:
            assert (
                web.get(f"http://{os.environ['RESTORE_MINIO']}:9000/{quote(bucket)}").status_code
                == 403
            )
            for asset in assets:
                STAGE = "OBJECT_BYTES_AND_VERSION"
                anonymous = web.get(
                    f"http://{os.environ['RESTORE_MINIO']}:9000/{quote(bucket)}/"
                    + quote(asset["object_key"], safe="/"),
                    params={"versionId": asset["object_version"]},
                )
                assert anonymous.status_code == 403, "Restored object permits anonymous reads"
                result = client.get_object(
                    Bucket=bucket, Key=asset["object_key"], VersionId=asset["object_version"]
                )
                stream = result["Body"]
                try:
                    assert hashlib.file_digest(stream, "sha256").hexdigest() == asset["sha256"]
                finally:
                    stream.close()
                signed = client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": bucket,
                        "Key": asset["object_key"],
                        "VersionId": asset["object_version"],
                    },
                    ExpiresIn=60,
                )
                STAGE = "SIGNED_OBJECT_READ"
                response = web.get(signed)
                assert (
                    response.status_code == 200
                    and hashlib.sha256(response.content).hexdigest() == asset["sha256"]
                )
            traccar = "http://" + os.environ["RESTORE_TRACCAR"] + ":8082"
            STAGE = "TRACCAR_READY"
            deadline = time.monotonic() + 120
            while True:
                try:
                    server = web.get(traccar + "/api/server")
                    server.raise_for_status()
                    break
                except httpx.HTTPError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Restored Traccar did not become ready") from None
                    time.sleep(1)
            auth = (os.environ["RESTORE_TRACCAR_EMAIL"], os.environ["RESTORE_TRACCAR_PASSWORD"])
            STAGE = "TRACCAR_AUTH_AND_GPS"
            devices = web.get(traccar + "/api/devices", auth=auth)
            devices.raise_for_status()
            positions = web.get(traccar + "/api/positions", auth=auth)
            positions.raise_for_status()
            identities = sorted((d["id"], d["uniqueId"]) for d in devices.json())
            position_ids = sorted(p["id"] for p in positions.json())
    finally:
        client.close()
    return {
        "migration_head": head,
        "table_fingerprints_verified": len(actual_tables),
        "private_versioned_assets_verified": len(assets),
        "original_object_version_ids_preserved": True if assets else None,
        "signed_read_after_restore": "PASS" if assets else "NOT_EXERCISED_NO_ASSETS",
        "anonymous_storage_read": 403,
        "anonymous_objects_tested": len(assets),
        "traccar_http": 200,
        "traccar_device_count": len(identities),
        "traccar_latest_positions_count": len(position_ids),
        "traccar_device_identities_sha256": hashlib.sha256(
            json.dumps(identities).encode()
        ).hexdigest(),
        "traccar_latest_position_ids_sha256": hashlib.sha256(
            json.dumps(position_ids).encode()
        ).hexdigest(),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(verify()))
    except Exception as error:
        # No exception message/traceback: these can contain URLs or credentials.
        print(
            "M8_RESTORE_DIAGNOSTIC "
            + json.dumps(
                {
                    "stage": STAGE,
                    "error_type": type(error).__name__,
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)
