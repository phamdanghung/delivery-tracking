import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import httpx
import pytest
import test_m1_api
from PIL import Image
from sqlalchemy import text
from test_m1_api import header
from test_m2_api import approved_fixture, command, order
from test_m4_api import planned

from app.config import get_settings
from app.pod_storage import storage_client

context = test_m1_api.context
pytestmark = pytest.mark.integration


def photo():
    output = BytesIO()
    Image.new("RGB", (12, 10), "blue").save(output, format="PNG")
    return output.getvalue()


def payload(stop, data, **changes):
    now = datetime.now(UTC).isoformat()
    return {
        "client_action_id": str(uuid4()),
        "trip_stop_id": stop["id"],
        "source": "CAMERA_CAPTURED",
        "captured_at": now,
        "sha256": hashlib.sha256(data).hexdigest(),
        "location_status": "VERIFIED",
        "latitude": 10.7,
        "longitude": 106.7,
        "gps_fix_at": now,
        "gps_freshness": "NORMAL",
        **changes,
    }


def upload(ctx, stop, data, metadata, role="DRIVER"):
    return ctx[0].post(
        f"/api/v1/deliveries/{stop['delivery_id']}/pod/photos",
        content=data,
        headers={
            **header(ctx[3], role),
            "Content-Type": "image/png",
            "X-POD-Metadata": json.dumps(metadata),
        },
    )


def delivering(ctx, stop):
    for old, new in [("EN_ROUTE", "ARRIVED"), ("ARRIVED", "DELIVERING")]:
        response = command(ctx, stop["delivery_id"], old, new, "DRIVER")
        assert response.status_code == 200, response.text


def test_real_private_upload_concurrent_replay_rbac_and_single_delivered_event(context):
    client, engine, _, tokens = context
    trip = planned(context)
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/start", headers=header(tokens, "DRIVER")
        ).status_code
        == 200
    )
    stop = trip["stops"][0]
    delivering(context, stop)
    data = photo()
    metadata = payload(stop, data)
    assert upload(context, stop, data, metadata, "ADMIN").status_code == 403
    assert upload(context, stop, data, metadata, "DISPATCHER").status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(context, stop, data, metadata), range(2)))
    assert all(response.status_code == 201 for response in responses), [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert upload(context, stop, data, {**metadata, "source": "ALBUM_SELECTED"}).status_code == 409
    identifier = responses[0].json()["id"]
    pod_command = {
        "client_action_id": metadata["client_action_id"],
        "occurred_at": metadata["captured_at"],
        "action": {"kind": "POD_UPLOAD", "resource_id": stop["delivery_id"], "data": metadata},
    }
    ack = client.post("/api/v1/driver/actions", json=pod_command, headers=header(tokens, "DRIVER"))
    assert ack.status_code == 200, ack.text
    assert (
        client.post(
            "/api/v1/driver/actions", json=pod_command, headers=header(tokens, "DRIVER")
        ).json()
        == ack.json()
    )
    settings = get_settings()
    storage = storage_client(settings)
    with engine.connect() as db:
        row = (
            db.execute(text("SELECT * FROM pod_photos WHERE id=:id"), {"id": identifier})
            .mappings()
            .one()
        )
        versions = storage.list_object_versions(Bucket=settings.s3_bucket, Prefix=row["object_key"])
        assert len(versions["Versions"]) == 1
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='POD_UPLOAD'"
                ),
                {"id": stop["delivery_id"]},
            )
            == 1
        )
    storage.close()
    url = client.get(
        f"/api/v1/deliveries/{stop['delivery_id']}/pod/photos/{identifier}/url",
        headers=header(tokens),
    ).json()["url"]
    assert httpx.get(url).status_code == 200
    assert httpx.get(url.split("?")[0]).status_code == 403
    cmd = {
        "client_action_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "action": {
            "kind": "STATUS",
            "resource_id": stop["delivery_id"],
            "data": {"from_status": "DELIVERING", "to_status": "DELIVERED"},
        },
    }
    first = client.post("/api/v1/driver/actions", json=cmd, headers=header(tokens, "DRIVER"))
    assert first.status_code == 200, first.text
    assert (
        client.post("/api/v1/driver/actions", json=cmd, headers=header(tokens, "DRIVER")).json()
        == first.json()
    )
    assert upload(context, stop, data, metadata).status_code == 201  # lost response, same ID
    with engine.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM delivery_status_events "
                    "WHERE delivery_id=:id AND to_status='DELIVERED'"
                ),
                {"id": stop["delivery_id"]},
            )
            == 1
        )


def test_missing_stale_invalid_gps_album_and_wrong_attempt(context):
    client, _, _, tokens = context
    trip = planned(context)
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/start", headers=header(tokens, "DRIVER")
        ).status_code
        == 200
    )
    for stop, freshness in zip(trip["stops"], ["MISSING", "STALE", "INVALID"], strict=True):
        delivering(context, stop)
        data = photo()
        metadata = payload(
            stop,
            data,
            source="ALBUM_SELECTED",
            latitude=None,
            longitude=None,
            gps_fix_at=None,
            gps_freshness=freshness,
            location_status="LOCATION_UNVERIFIED",
            location_reason="Không có GPS hợp lệ",
        )
        assert upload(context, stop, data, {**metadata, "location_reason": ""}).status_code == 422
        assert (
            upload(context, stop, data, {**metadata, "trip_stop_id": str(uuid4())}).status_code
            == 409
        )
        response = upload(context, stop, data, metadata)
        assert response.status_code == 201, response.text
        assert response.json()["location_status"] == "LOCATION_UNVERIFIED"
        assert (
            command(context, stop["delivery_id"], "DELIVERING", "DELIVERED", "DRIVER").status_code
            == 200
        )


def test_reschedule_new_attempt_requires_new_pod_and_keeps_old_history(context):
    client, engine, _, tokens = context
    item, trip = approved_fixture(context)
    stop = trip["stops"][0]
    delivering(context, stop)
    data = photo()
    old_metadata = payload(stop, data)
    assert upload(context, stop, data, old_metadata).status_code == 201
    assert (
        command(
            context, item["id"], "DELIVERING", "FAILED", "DRIVER", reason="Khách vắng"
        ).status_code
        == 200
    )
    values = order()
    commitment = {
        key: values[key] for key in ["commitment_type", "scheduled_date", "appointment_at"]
    }
    result = client.post(
        f"/api/v1/deliveries/{item['id']}/reschedule",
        headers=header(tokens),
        json={"commitment": commitment},
    )
    assert result.status_code == 200, result.text
    response = client.post(
        "/api/v1/trips",
        headers=header(tokens),
        json={
            "trip_date": values["scheduled_date"],
            "vehicle_id": trip["vehicle_id"],
            "driver_id": trip["driver_id"],
            "delivery_ids": [item["id"]],
            "start": {"latitude": 10.8, "longitude": 106.8},
            "end": {"latitude": 10.8, "longitude": 106.8},
        },
    )
    assert response.status_code == 201, response.text
    new_trip = response.json()
    # Isolated approved fixture; M3 optimization is separately covered, never promote dev records.
    with engine.begin() as db:
        db.execute(text("UPDATE trips SET status='PLANNED' WHERE id=:id"), {"id": new_trip["id"]})
        db.execute(text("UPDATE deliveries SET status='ASSIGNED' WHERE id=:id"), {"id": item["id"]})
        db.execute(
            text("UPDATE trip_stops SET status='ASSIGNED' WHERE trip_id=:id"),
            {"id": new_trip["id"]},
        )
    assert (
        client.post(
            f"/api/v1/trips/{new_trip['id']}/start", headers=header(tokens, "DRIVER")
        ).status_code
        == 200
    )
    new_stop = new_trip["stops"][0]
    delivering(context, new_stop)
    assert command(context, item["id"], "DELIVERING", "DELIVERED", "DRIVER").status_code == 409
    assert upload(context, new_stop, data, payload(stop, data)).status_code == 409
    assert upload(context, new_stop, data, payload(new_stop, data)).status_code == 201
    assert command(context, item["id"], "DELIVERING", "DELIVERED", "DRIVER").status_code == 200
    history = client.get(
        f"/api/v1/deliveries/{item['id']}/pod/photos", headers=header(tokens)
    ).json()
    assert {row["trip_stop_id"] for row in history} == {stop["id"], new_stop["id"]}
