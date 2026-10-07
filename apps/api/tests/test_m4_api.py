from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import test_m1_api
from sqlalchemy import text
from test_m1_api import header
from test_m3_api import approve, optimize, route_trip

from app.gps import ingest

context = test_m1_api.context
pytestmark = pytest.mark.integration


def planned(ctx):
    trip, departure = route_trip(ctx)
    plan = optimize(ctx, trip, departure).json()
    assert approve(ctx, trip, plan).status_code == 200
    return trip


def command(kind, resource, data=None):
    return {
        "client_action_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "action": {"kind": kind, "resource_id": resource, **({"data": data} if data else {})},
    }


def send(ctx, body):
    return ctx[0].post("/api/v1/driver/actions", json=body, headers=header(ctx[3], "DRIVER"))


def test_durable_replay_concurrent_start_order_and_scope(context):
    client, engine, _, tokens = context
    trip = planned(context)
    cmd = command("START_TRIP", trip["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: send(context, cmd), range(2)))
    assert all(x.status_code == 200 for x in responses)
    assert responses[0].json() == responses[1].json()
    assert send(context, cmd).json() == responses[0].json()
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM driver_action_receipts WHERE client_action_id=:id"),
                {"id": cmd["client_action_id"]},
            )
            == 1
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='START'"),
                {"id": trip["id"]},
            )
            == 1
        )
    changed = {**cmd, "occurred_at": datetime.now(UTC).isoformat()}
    assert send(context, changed).status_code == 409
    assert client.get("/api/v1/driver/today", headers=header(tokens)).status_code == 403
    assert client.get("/api/v1/driver/today", headers=header(tokens, "DRIVER")).status_code == 200
    stop = trip["stops"][0]
    bad = command(
        "STATUS", stop["delivery_id"], {"from_status": "ARRIVED", "to_status": "DELIVERING"}
    )
    result = send(context, bad)
    assert result.status_code == 409
    assert send(context, bad).json() == result.json()
    cancelled = command(
        "STATUS",
        stop["delivery_id"],
        {"from_status": "EN_ROUTE", "to_status": "CANCELLED", "reason": "No"},
    )
    assert send(context, cancelled).status_code == 403


def move(ctx, trip, distance, *, stale=False, valid=True):
    engine = ctx[1]
    with engine.begin() as db:
        device = db.scalar(
            text("SELECT traccar_device_id FROM vehicles WHERE id=:id"), {"id": trip["vehicle_id"]}
        )
        if device is None:
            device = int(uuid4().hex[:10], 16)
            db.execute(
                text("UPDATE vehicles SET traccar_device_id=:device WHERE id=:id"),
                {"device": device, "id": trip["vehicle_id"]},
            )
        point = db.execute(
            text("""SELECT ST_Y(p::geometry),ST_X(p::geometry) FROM
          (SELECT ST_Project(d.location,:distance,0) p FROM deliveries d
           WHERE d.id=:id) q"""),
            {"distance": distance, "id": trip["stops"][0]["delivery_id"]},
        ).one()
        now = datetime.now(UTC)
        raw = {
            "id": int(uuid4().hex[:12], 16),
            "deviceId": device,
            "valid": valid,
            "fixTime": (now - timedelta(seconds=31) if stale else now).isoformat(),
            "serverTime": now.isoformat(),
            "latitude": point[0],
            "longitude": point[1],
            "speed": 0,
            "course": 0,
            "attributes": {"ignition": True},
        }
        ingest(db, raw)
    return raw


def test_real_postgis_geofence_hysteresis_and_offline_correction_replay(context):
    client, engine, _, tokens = context
    trip = planned(context)
    assert send(context, command("START_TRIP", trip["id"])).status_code == 200
    delivery_id = trip["stops"][0]["delivery_id"]

    def detail():
        return client.get(
            f"/api/v1/deliveries/{delivery_id}", headers=header(tokens, "DRIVER")
        ).json()

    move(context, trip, 90)
    move(context, trip, 50.01)
    assert detail()["delivery"]["status"] == "EN_ROUTE"
    move(context, trip, 49.99, stale=True)
    move(context, trip, 49.99, valid=False)
    assert detail()["delivery"]["status"] == "EN_ROUTE"
    raw = move(context, trip, 49.99)
    with engine.begin() as db:
        assert not ingest(db, raw)
    move(context, trip, 10)
    before = detail()
    assert before["delivery"]["status"] == "ARRIVED"
    arrivals = [x for x in before["events"] if x["to_status"] == "ARRIVED"]
    assert len(arrivals) == 1 and arrivals[0]["source"] == "GEOFENCE"
    bad = command(
        "CORRECT_ARRIVED", delivery_id, {"arrival_event_id": arrivals[0]["id"], "reason": " "}
    )
    assert send(context, bad).status_code == 422
    correction = command(
        "CORRECT_ARRIVED",
        delivery_id,
        {"arrival_event_id": arrivals[0]["id"], "reason": "GPS nhận sai"},
    )
    assert send(context, correction).status_code == 200
    assert send(context, correction).status_code == 200
    move(context, trip, 10)
    move(context, trip, 60)
    move(context, trip, 69.99)
    move(context, trip, 10)
    assert detail()["delivery"]["status"] == "EN_ROUTE"
    move(context, trip, 70.01)
    assert detail()["delivery"]["status"] == "EN_ROUTE"
    move(context, trip, 49.99)
    after = detail()
    assert after["delivery"]["status"] == "ARRIVED"
    assert len([x for x in after["events"] if x["to_status"] == "ARRIVED"]) == 2
    # An old cached correction must not reverse the second arrival.
    old = {**correction, "client_action_id": str(uuid4())}
    assert send(context, old).status_code == 409
    arrival = next(x for x in reversed(after["events"]) if x["to_status"] == "ARRIVED")
    response = client.post(
        f"/api/v1/deliveries/{delivery_id}/arrival-correction",
        headers=header(tokens, "DISPATCHER"),
        json={"arrival_event_id": arrival["id"], "reason": "Điều phối xác minh"},
    )
    assert response.status_code == 200, response.text
    with engine.connect() as db:
        assert (
            db.scalar(text("SELECT status::text FROM trips WHERE id=:id"), {"id": trip["id"]})
            == "ACTIVE"
        )
        audits = (
            db.execute(
                text("SELECT * FROM audit_logs WHERE resource_id=:id AND action='CORRECT_ARRIVED'"),
                {"id": delivery_id},
            )
            .mappings()
            .all()
        )
        assert len(audits) == 2
        assert all(
            x["actor_user_id"]
            and x["reason"]
            and x["created_at"]
            and x["before_json"]["status"] == "ARRIVED"
            and x["after_json"]["status"] == "EN_ROUTE"
            for x in audits
        )
