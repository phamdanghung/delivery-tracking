from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_m1_api import context as context
from test_m1_api import header
from test_m7_fuel_api import vehicle

from app.maintenance import traccar_odometer

pytestmark = pytest.mark.integration


def test_traccar_odometer_trusted_source_dedup_and_rejected_observations(context):
    client, engine, _, tokens = context
    vid = vehicle(context)
    now = datetime.now(UTC)
    position = {"valid": True, "freshness": "NORMAL", "gps_at": now, "position_id": 741}
    with engine.begin() as db:
        for attributes in (None, {}, {"totalDistance": 500000}, {"odometer": "NaN"}):
            traccar_odometer(db, vid, position, {"attributes": attributes})
        for rejected in ({**position, "valid": False}, {**position, "freshness": "STALE"}):
            traccar_odometer(db, vid, rejected, {"attributes": {"odometer": 11000000}})
        assert (
            db.scalar(
                text("SELECT count(*) FROM vehicle_odometer_readings WHERE vehicle_id=:id"),
                {"id": vid},
            )
            == 0
        )
        for _ in range(2):
            traccar_odometer(db, vid, position, {"attributes": {"odometer": 11000000}})
        assert (
            db.scalar(
                text("SELECT count(*) FROM vehicle_odometer_readings WHERE vehicle_id=:id"),
                {"id": vid},
            )
            == 1
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_logs WHERE resource_type='odometer_reading' "
                    "AND action='OBSERVE' AND after_json->>'position_id'='741'"
                )
            )
            == 1
        )
    reading = client.get(
        "/api/v1/maintenance/odometer-readings", headers=header(tokens), params={"vehicle_id": vid}
    )
    assert reading.status_code == 200, reading.text
    assert reading.json()[0]["source"] == "TRACCAR"
    assert float(reading.json()[0]["odometer_km"]) == 11000


def test_per_vehicle_rules_permissions_missing_reading_and_service_reset(context):
    client, engine, _, tokens = context
    first, second = vehicle(context), vehicle(context)
    now = datetime.now(UTC)
    day = now.astimezone().date().isoformat()
    body = {
        "vehicle_id": first,
        "task_type": "OIL",
        "interval_km": 1000,
        "lead_km": 100,
        "interval_days": 30,
        "lead_days": 5,
        "baseline_date": day,
        "baseline_odometer_km": "10000",
        "baseline_source": "ADMIN",
    }
    for role in ("DRIVER", "DISPATCHER"):
        assert (
            client.post(
                "/api/v1/maintenance/rules", headers=header(tokens, role), json=body
            ).status_code
            == 403
        )
    assert (
        client.post(
            "/api/v1/maintenance/rules", headers=header(tokens), json={**body, "lead_km": None}
        ).status_code
        == 422
    )
    created = client.post("/api/v1/maintenance/rules", headers=header(tokens), json=body)
    assert created.status_code == 201, created.text
    rule = created.json()
    alternate = client.post(
        "/api/v1/maintenance/rules",
        headers=header(tokens),
        json={**body, "vehicle_id": second, "interval_km": 2000},
    ).json()

    def status(vid):
        result = client.get(
            "/api/v1/maintenance/status",
            headers=header(tokens, "DISPATCHER"),
            params={"vehicle_id": vid},
        )
        assert result.status_code == 200, result.text
        return result.json()[0]["assessment"]

    assert status(first)["status"] == "INSUFFICIENT"
    for vid in (first, second):
        result = client.post(
            "/api/v1/maintenance/odometer-readings",
            headers=header(tokens),
            json={
                "vehicle_id": vid,
                "odometer_km": "11000",
                "observed_at": now.isoformat(),
                "reason": "Đọc đồng hồ thực tế",
            },
        )
        assert result.status_code == 201, result.text
        assert result.json()["source"] == "ADMIN"
    assert status(first)["status"] == "DUE"
    assert status(second)["status"] == "NOT_DUE"
    event = {
        "client_action_id": str(uuid4()),
        "vehicle_id": first,
        "rule_id": rule["id"],
        "service_date": day,
        "odometer_km": "11000",
        "odometer_source": "ADMIN",
        "cost": "200000",
        "note": "Thay dầu",
    }
    assert (
        client.post(
            "/api/v1/maintenance/events", headers=header(tokens, "DISPATCHER"), json=event
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/maintenance/events",
            headers=header(tokens),
            json={**event, "rule_id": alternate["id"]},
        ).status_code
        == 422
    )
    saved = client.post("/api/v1/maintenance/events", headers=header(tokens), json=event)
    assert saved.status_code == 201, saved.text
    assert status(first)["status"] == "NOT_DUE"
    assert status(first)["baseline_event_id"] == saved.json()["id"]
    assert (
        client.get("/api/v1/maintenance/events", headers=header(tokens, "DRIVER")).status_code
        == 403
    )
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='CREATE'"),
                {"id": saved.json()["id"]},
            )
            == 1
        )


def test_documents_expiry_config_and_audited_changes(context):
    client, engine, _, tokens = context
    vid = vehicle(context)
    day = datetime.now().date()
    body = {
        "vehicle_id": vid,
        "doc_type": "INSURANCE",
        "expiry_date": (day + timedelta(days=5)).isoformat(),
        "lead_days": 7,
    }
    assert (
        client.post(
            "/api/v1/vehicle-documents", headers=header(tokens, "DISPATCHER"), json=body
        ).status_code
        == 403
    )
    result = client.post("/api/v1/vehicle-documents", headers=header(tokens), json=body)
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["status"] == "SOON"
    result = client.patch(
        "/api/v1/vehicle-documents/" + data["id"],
        headers=header(tokens),
        json={
            **body,
            "expiry_date": (day - timedelta(days=1)).isoformat(),
            "reason": "Sửa ngày trên chứng từ",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "OVERDUE"
    assert (
        client.get("/api/v1/vehicle-documents", headers=header(tokens, "DRIVER")).status_code == 403
    )
    with engine.connect() as db:
        audit = db.execute(
            text("SELECT after_json FROM audit_logs WHERE resource_id=:id AND action='UPDATE'"),
            {"id": data["id"]},
        ).scalar_one()
        assert audit["reason"] == "Sửa ngày trên chứng từ"
