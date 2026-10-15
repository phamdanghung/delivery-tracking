import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from test_m1_api import context as context
from test_m1_api import header
from test_m5_api import photo
from test_m7_fuel_api import vehicle

from app.config import get_settings
from app.pod_storage import storage_client

pytestmark = pytest.mark.integration


def trip(ctx):
    vid = vehicle(ctx)
    with ctx[1].begin() as db:
        profile = db.scalar(
            text(
                "INSERT INTO driver_profiles(user_id) VALUES (:user) "
                "ON CONFLICT(user_id) DO UPDATE SET active=true RETURNING id"
            ),
            {"user": ctx[2]["DRIVER"]["id"]},
        )
        return str(
            db.scalar(
                text(
                    "INSERT INTO trips(trip_date,vehicle_id,driver_id,status) "
                    "VALUES (CURRENT_DATE,:vehicle,:driver,'ACTIVE') RETURNING id"
                ),
                {"vehicle": vid, "driver": profile},
            )
        )


def command(tid, **changes):
    data = {
        "type": "TOLL",
        "amount": "10000",
        "incurred_at": datetime.now(UTC).isoformat(),
        "note": "Phí đường",
        **changes,
    }
    return {
        "client_action_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "action": {"kind": "EXPENSE_CREATE", "resource_id": tid, "data": data},
    }


def test_expense_offline_replay_concurrency_rbac_and_no_other_driver_cost(context):
    client, engine, records, tokens = context
    tid = trip(context)
    cmd = command(tid)

    def send(body):
        return client.post("/api/v1/driver/actions", headers=header(tokens, "DRIVER"), json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, [cmd, cmd]))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    expense = responses[0].json()
    assert responses[1].json() == expense == send(cmd).json()
    assert (
        send(
            {
                **cmd,
                "action": {**cmd["action"], "data": {**cmd["action"]["data"], "amount": "20000"}},
            }
        ).status_code
        == 409
    )
    body = {**cmd["action"]["data"], "trip_id": tid, "client_action_id": str(uuid4())}
    assert client.post("/api/v1/expenses", headers=header(tokens), json=body).status_code == 403
    another = client.post("/api/v1/expenses", headers=header(tokens, "DISPATCHER"), json=body)
    assert another.status_code == 201, another.text
    own = client.get("/api/v1/expenses", headers=header(tokens, "DRIVER"), params={"trip_id": tid})
    assert own.status_code == 200
    assert own.headers["cache-control"] == "no-store"
    assert [row["id"] for row in own.json()] == [expense["id"]]
    assert (
        client.get(
            "/api/v1/expenses/" + another.json()["id"], headers=header(tokens, "DRIVER")
        ).status_code
        == 404
    )
    assert (
        len(client.get("/api/v1/expenses", headers=header(tokens), params={"trip_id": tid}).json())
        == 2
    )
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='CREATE'"),
                {"id": expense["id"]},
            )
            == 1
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM driver_action_receipts "
                    "WHERE actor_user_id=:actor AND client_action_id=:id"
                ),
                {"actor": records["DRIVER"]["id"], "id": cmd["client_action_id"]},
            )
            == 1
        )


def test_private_receipt_immutable_upload_and_same_command_scope(context):
    client, engine, _, tokens = context
    tid = trip(context)
    image = photo()
    cmd = command(tid)
    metadata = {
        "trip_id": tid,
        "client_action_id": cmd["client_action_id"],
        "sha256": hashlib.sha256(image).hexdigest(),
        "content_type": "image/png",
        "source": "ALBUM_SELECTED",
        "captured_at": datetime.now(UTC).isoformat(),
    }

    def upload(value):
        return client.post(
            "/api/v1/expense-receipts",
            headers={
                **header(tokens, "DRIVER"),
                "content-type": "image/png",
                "x-receipt-metadata": json.dumps(value),
            },
            content=image,
        )

    initial = upload(metadata)
    assert initial.status_code == 201, initial.text
    assert upload(metadata).json() == initial.json()
    assert upload({**metadata, "source": "CAMERA_CAPTURED"}).status_code == 409
    cmd["action"]["data"]["receipt_metadata"] = metadata
    saved = client.post("/api/v1/driver/actions", headers=header(tokens, "DRIVER"), json=cmd)
    assert saved.status_code == 200, saved.text
    assert saved.json()["receipt_id"] == initial.json()["id"]
    urlpath = "/api/v1/expenses/" + saved.json()["id"] + "/receipt-url"
    assert client.get(urlpath).status_code == 401
    signed = client.get(urlpath, headers=header(tokens))
    assert signed.status_code == 200, signed.text
    assert signed.json()["expires_in"] == get_settings().pod_read_url_seconds
    with httpx.Client(trust_env=False, timeout=15) as http:
        content = http.get(signed.json()["url"])
        assert (
            content.status_code == 200
            and hashlib.sha256(content.content).hexdigest() == initial.json()["sha256"]
        )
        assert http.get(signed.json()["url"].split("?", 1)[0].split("?", 1)[0]).status_code == 403
    with engine.connect() as db:
        row = db.execute(
            text("SELECT object_key FROM expense_receipts WHERE id=:id"),
            {"id": initial.json()["id"]},
        ).scalar_one()
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='UPLOAD'"),
                {"id": initial.json()["id"]},
            )
            == 1
        )
    storage = storage_client(get_settings())
    try:
        versions = storage.list_object_versions(Bucket=get_settings().s3_bucket, Prefix=row)
        assert len(versions["Versions"]) == 1
    finally:
        storage.close()
    # Changing command ID never borrows the earlier command's receipt metadata.
    other = command(tid, receipt_metadata=metadata)
    assert (
        client.post(
            "/api/v1/driver/actions", headers=header(tokens, "DRIVER"), json=other
        ).status_code
        == 409
    )
