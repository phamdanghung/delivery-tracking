import hashlib
import json
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


@pytest.mark.parametrize("kind,role", [("FUEL", "DISPATCHER"), ("MAINTENANCE", "ADMIN")])
def test_optional_vehicle_evidence_private_scoped_versioned_and_idempotent(context, kind, role):
    client, engine, _, tokens = context
    vid = vehicle(context)
    image = photo()
    nonce = str(uuid4())
    at = datetime.now(UTC).isoformat()
    meta = {
        "vehicle_id": vid,
        "kind": kind,
        "client_action_id": nonce,
        "content_type": "image/png",
        "sha256": hashlib.sha256(image).hexdigest(),
        "source": "ALBUM_SELECTED",
        "captured_at": at,
    }

    def upload(actor, value=meta):
        return client.post(
            "/api/v1/vehicle-receipts",
            headers={
                **header(tokens, actor),
                "content-type": "image/png",
                "x-receipt-metadata": json.dumps(value),
            },
            content=image,
        )

    assert upload("DRIVER").status_code == 403
    if kind == "MAINTENANCE":
        assert upload("DISPATCHER").status_code == 403
    initial = upload(role)
    assert initial.status_code == 201, initial.text
    assert upload(role).json() == initial.json()
    assert upload(role, {**meta, "source": "CAMERA_CAPTURED"}).status_code == 409
    if kind == "FUEL":
        endpoint = "/api/v1/fuel/entries"
        values = {
            "vehicle_id": vid,
            "client_action_id": nonce,
            "liters": "5",
            "amount": "100000",
            "filled_at": at,
            "receipt_metadata": meta,
        }
    else:
        rule = client.post(
            "/api/v1/maintenance/rules",
            headers=header(tokens),
            json={
                "vehicle_id": vid,
                "task_type": "OIL",
                "interval_days": 30,
                "lead_days": 5,
                "baseline_date": at[:10],
                "baseline_source": "ADMIN",
            },
        )
        assert rule.status_code == 201, rule.text
        endpoint = "/api/v1/maintenance/events"
        values = {
            "vehicle_id": vid,
            "client_action_id": nonce,
            "rule_id": rule.json()["id"],
            "service_date": at[:10],
            "note": "Thay dầu",
            "receipt_metadata": meta,
        }
    saved = client.post(endpoint, headers=header(tokens, role), json=values)
    assert saved.status_code == 201, saved.text
    assert client.post(endpoint, headers=header(tokens, role), json=values).json() == saved.json()
    assert saved.json()["receipt_id"] == initial.json()["id"]
    if kind == "FUEL":
        changed = client.patch(
            endpoint + "/" + saved.json()["id"],
            headers=header(tokens),
            json={
                "vehicle_id": vid,
                "liters": "5",
                "amount": "100000",
                "filled_at": at,
                "note": "Bổ sung ghi chú",
                "reason": "Cập nhật thông tin",
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["receipt_id"] == initial.json()["id"]
        assert (
            client.post(
                endpoint, headers=header(tokens, role), json={**values, "liters": "6"}
            ).status_code
            == 409
        )
    urlpath = endpoint + "/" + saved.json()["id"] + "/receipt-url"
    assert client.get(urlpath).status_code == 401
    assert client.get(urlpath, headers=header(tokens, "DRIVER")).status_code == 403
    signed = client.get(urlpath, headers=header(tokens, "DISPATCHER"))
    assert signed.status_code == 200, signed.text
    with httpx.Client(timeout=15, trust_env=False) as http:
        response = http.get(signed.json()["url"])
        assert (
            response.status_code == 200
            and hashlib.sha256(response.content).hexdigest() == initial.json()["sha256"]
        )
        assert http.get(signed.json()["url"].split("?", 1)[0]).status_code == 403
    with engine.connect() as db:
        row = db.execute(
            text("SELECT object_key FROM vehicle_receipts WHERE id=:id"),
            {"id": initial.json()["id"]},
        ).scalar_one()
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='UPLOAD'"),
                {"id": initial.json()["id"]},
            )
            == 1
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='CREATE'"),
                {"id": saved.json()["id"]},
            )
            == 1
        )
    storage = storage_client(get_settings())
    try:
        assert (
            len(
                storage.list_object_versions(Bucket=get_settings().s3_bucket, Prefix=row)[
                    "Versions"
                ]
            )
            == 1
        )
    finally:
        storage.close()
    wrong = {**values, "vehicle_id": vehicle(context), "client_action_id": str(uuid4())}
    assert client.post(endpoint, headers=header(tokens, role), json=wrong).status_code in (409, 422)
