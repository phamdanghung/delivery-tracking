from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from test_m1_api import context as context
from test_m1_api import header
from test_m7_fuel_api import vehicle

from app.gps import ingest
from app.safety import process_safety_position

pytestmark = pytest.mark.integration


def test_speed_incident_dedup_stale_rbac_resolution_and_new_episode(context):
    client, engine, _, tokens = context
    vid = vehicle(context)
    body = {
        "speed_limit_kmh": "20",
        "outside_hours_enabled": False,
        "reason": "Ngưỡng đã cấu hình cho xe test",
    }
    for role in ("DISPATCHER", "DRIVER"):
        assert (
            client.patch(
                "/api/v1/safety/configs/" + vid, headers=header(tokens, role), json=body
            ).status_code
            == 403
        )
    configured = client.patch("/api/v1/safety/configs/" + vid, headers=header(tokens), json=body)
    assert configured.status_code == 200, configured.text
    device = 987654
    now = datetime.now(UTC)
    with engine.begin() as db:
        db.execute(
            text("UPDATE vehicles SET traccar_device_id=:device WHERE id=:id"),
            {"device": device, "id": vid},
        )

        def raw(pid, age, speed):
            at = now - timedelta(seconds=age)
            return {
                "id": pid,
                "deviceId": device,
                "valid": True,
                "latitude": 10.7,
                "longitude": 106.7,
                "speed": speed,
                "course": 0,
                "fixTime": at.isoformat(),
                "serverTime": at.isoformat(),
                "attributes": {"ignition": True},
            }

        assert ingest(db, raw(1, 25, 20))
        assert not ingest(db, raw(1, 25, 20))  # same position through REST/socket
        assert ingest(db, raw(2, 24, 22))
    result = client.get("/api/v1/safety/alerts", headers=header(tokens), params={"vehicle_id": vid})
    assert result.status_code == 200, result.text
    assert len(result.json()) == 1
    alert = result.json()[0]
    assert alert["status"] == "NEW"
    url = "/api/v1/safety/alerts/" + alert["id"] + "/state"
    assert (
        client.patch(
            url, headers=header(tokens, "DRIVER"), json={"from_state": "NEW", "to_state": "SEEN"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            url,
            headers=header(tokens),
            json={"from_state": "NEW", "to_state": "RESOLVED", "reason": "Skip"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            url,
            headers=header(tokens, "DISPATCHER"),
            json={"from_state": "NEW", "to_state": "SEEN"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            url, headers=header(tokens), json={"from_state": "SEEN", "to_state": "RESOLVED"}
        ).status_code
        == 422
    )
    resolved = client.patch(
        url,
        headers=header(tokens),
        json={"from_state": "SEEN", "to_state": "RESOLVED", "reason": "Đã trao đổi tài xế"},
    )
    assert resolved.status_code == 200, resolved.text
    with engine.begin() as db:
        assert ingest(db, raw(3, 23, 24))
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 1
        )
        assert ingest(db, raw(4, 22, 0))
        assert ingest(db, raw(5, 21, 24))
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 2
        )
        actions = (
            db.execute(
                text("SELECT action FROM audit_logs WHERE resource_id=:id ORDER BY created_at"),
                {"id": alert["id"]},
            )
            .scalars()
            .all()
        )
        assert actions == ["CREATE", "SEEN", "RESOLVED", "INCIDENT_ENDED"]
        assert (
            db.scalar(
                text("SELECT reason FROM audit_logs WHERE resource_id=:id AND action='RESOLVED'"),
                {"id": alert["id"]},
            )
            == "Đã trao đổi tài xế"
        )
    assert client.get("/api/v1/safety/alerts", headers=header(tokens, "DRIVER")).status_code == 403


def test_outside_hours_requires_activity_trust_exceptions_and_incidents(context):
    client, engine, _, tokens = context
    vid = vehicle(context)
    # Deterministic source observations in an isolated real DB; real clock is not
    # substituted for stack/Traccar acceptance. These exercise all local boundaries.
    at = datetime(2026, 10, 13, 11, tzinfo=UTC)  # 18:00 local

    def position(pid, acc=False, speed=0, freshness="NORMAL", valid=True, when=at):
        return {
            "position_id": pid,
            "gps_at": when,
            "acc": acc,
            "speed_kmh": speed,
            "valid": valid,
            "freshness": freshness,
        }

    with engine.begin() as db:
        process_safety_position(db, vid, position(1))
        process_safety_position(db, vid, position(2, acc=None))
        process_safety_position(db, vid, position(3, acc=True, freshness="STALE"))
        process_safety_position(db, vid, position(4, acc=True, valid=False))
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 0
        )
        process_safety_position(db, vid, position(5, acc=True))
        process_safety_position(db, vid, position(6, acc=True, when=at + timedelta(seconds=1)))
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 1
        )
        process_safety_position(
            db, vid, position(7, acc=True, when=datetime(2026, 10, 14, 0, 30, tzinfo=UTC))
        )
        process_safety_position(
            db, vid, position(8, acc=None, speed=5, when=at + timedelta(days=1))
        )
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 2
        )
    exception = {
        "vehicle_id": vid,
        "type": "OUTSIDE_HOURS",
        "from_at": (at + timedelta(days=2)).isoformat(),
        "to_at": (at + timedelta(days=2, hours=1)).isoformat(),
        "reason": "Giao ngoài giờ được duyệt",
    }
    assert (
        client.post(
            "/api/v1/safety/exceptions", headers=header(tokens, "DISPATCHER"), json=exception
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/safety/exceptions", headers=header(tokens), json={**exception, "to_at": None}
        ).status_code
        == 422
    )
    saved = client.post("/api/v1/safety/exceptions", headers=header(tokens), json=exception)
    assert saved.status_code == 201, saved.text
    with engine.begin() as db:
        process_safety_position(db, vid, position(9, acc=True, when=at + timedelta(days=2)))
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 2
        )
    voided = client.post(
        "/api/v1/safety/exceptions/" + saved.json()["id"] + "/void",
        headers=header(tokens),
        json={"reason": "Hủy kế hoạch ngoài giờ"},
    )
    assert voided.status_code == 200
    with engine.begin() as db:
        process_safety_position(
            db, vid, position(10, acc=True, when=at + timedelta(days=2, seconds=1))
        )
        assert (
            db.scalar(text("SELECT count(*) FROM safety_alerts WHERE vehicle_id=:id"), {"id": vid})
            == 3
        )
