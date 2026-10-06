import os
from datetime import datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
import test_m1_api
from sqlalchemy import text
from test_m1_api import header
from test_m2_api import create, order

from app.config import get_settings

context = test_m1_api.context
pytestmark = pytest.mark.integration


def test_thirty_stops_real_route_within_locked_five_second_target(context):
    trip, departure = route_trip(context, count=30)
    started = monotonic()
    response = optimize(context, trip, departure)
    elapsed = monotonic() - started
    assert response.status_code == 200, response.text
    assert len(response.json()["stops"]) == 30
    assert elapsed < 5, f"Real OSRM + solver + persistence: {elapsed:.3f}s"
    print(f"30 stops / 1 vehicle, actual OSRM/PostGIS, {elapsed:.3f}s")


def route_trip(ctx, count=3, late=False):
    assert os.environ.get("OSRM_URL"), "Real self-hosted OSRM is mandatory"
    when = datetime.fromisoformat(order()["appointment_at"])
    departure = when - timedelta(hours=1)
    items = []
    for index in range(count):
        kind = ["FIXED_TIME", "TIME_WINDOW", "BEFORE_DEADLINE"][index % 3]
        changes = {"latitude": 10.7769 + index * 0.001, "longitude": 106.7009 + index * 0.001}
        if count > 3:
            kind = "TIME_WINDOW"
            changes.update(
                window_start=departure.isoformat(),
                window_end=(departure + timedelta(hours=12)).isoformat(),
            )
        if late:
            kind = "BEFORE_DEADLINE"
            changes["deadline_at"] = (departure - timedelta(minutes=5)).isoformat()
        items.append(create(ctx, kind=kind, **changes))
    vehicle = (
        ctx[0]
        .post(
            "/api/v1/vehicles",
            headers=header(ctx[3]),
            json={"plate_no": uuid4().hex, "max_weight_kg": 10, "max_volume_m3": 1},
        )
        .json()
    )
    with ctx[1].begin() as db:
        profile = db.scalar(
            text("""INSERT INTO driver_profiles(user_id) VALUES (:user)
            ON CONFLICT (user_id) DO UPDATE SET active=true RETURNING id"""),
            {"user": ctx[2]["DRIVER"]["id"]},
        )
    data = {
        "trip_date": items[0]["scheduled_date"],
        "vehicle_id": vehicle["id"],
        "driver_id": str(profile),
        "delivery_ids": [x["id"] for x in items],
        "start": {"latitude": 10.7769, "longitude": 106.7009},
        "end": {"latitude": 10.7769, "longitude": 106.7009},
    }
    response = ctx[0].post("/api/v1/trips", headers=header(ctx[3], "DISPATCHER"), json=data)
    assert response.status_code == 201, response.text
    return response.json(), departure.isoformat()


def optimize(ctx, trip, departure, **changes):
    return ctx[0].post(
        f"/api/v1/trips/{trip['id']}/optimize",
        headers=header(ctx[3], "DISPATCHER"),
        json={"planned_departure_at": departure, **changes},
    )


def approve(ctx, trip, plan, **changes):
    return ctx[0].post(
        f"/api/v1/trips/{trip['id']}/approve",
        headers=header(ctx[3], "DISPATCHER"),
        json={"plan_id": plan["id"], **changes},
    )


def test_real_osrm_multistop_three_vehicles_approval_overload_and_driver_visibility(context):
    client, engine, _, tokens = context
    vehicles = set()
    for _ in range(3):
        trip, departure = route_trip(context)
        vehicles.add(trip["vehicle_id"])
        assert trip["warnings"]  # test fleet capacity deliberately below load
        response = optimize(context, trip, departure, service_seconds={trip["stops"][0]["id"]: 60})
        assert response.status_code == 200, response.text
        plan = response.json()
        assert len(plan["stops"]) == 3
        assert {s["delivery_id"] for s in plan["stops"]} == {
            s["delivery_id"] for s in trip["stops"]
        }
        assert plan["time_feasible"] and plan["approval_allowed"]
        assert (
            len(plan["geometry"]["coordinates"]) > 3
        )  # real road geometry, not straight-line mock
        assert plan["route_detail"]["legs"] and plan["distance_m"] > 0
        assert plan["warnings"]
        assert sum(s["service_seconds"] == 60 for s in plan["stops"]) == 1
        assert (
            client.get(f"/api/v1/trips/{trip['id']}", headers=header(tokens, "DRIVER")).status_code
            == 403
        )
        assert approve(context, trip, plan).status_code == 200
        assert (
            client.get(f"/api/v1/trips/{trip['id']}", headers=header(tokens, "DRIVER")).json()[
                "status"
            ]
            == "PLANNED"
        )
        assert approve(context, trip, plan).status_code == 409
        assert optimize(context, trip, departure).status_code == 409
        with engine.connect() as db:
            assert (
                db.scalar(
                    text(
                        """SELECT count(*) FROM delivery_status_events WHERE to_status='ASSIGNED'
                        AND delivery_id IN (SELECT delivery_id FROM trip_stops WHERE trip_id=:id)"""
                    ),
                    {"id": trip["id"]},
                )
                == 3
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM audit_logs WHERE action='APPROVE' AND resource_id=:id"
                    ),
                    {"id": trip["id"]},
                )
                == 1
            )
    assert len(vehicles) == 3


def test_infeasible_result_persisted_with_amount_no_override_or_approval(context):
    trip, departure = route_trip(context, late=True)
    response = optimize(context, trip, departure)
    assert response.status_code == 422, response.text
    plan = response.json()
    assert len(plan["stops"]) == 3
    assert not plan["time_feasible"] and not plan["approval_allowed"]
    assert all(s["violation"] == "LATE" and s["violation_seconds"] >= 300 for s in plan["stops"])
    saved = context[0].get(f"/api/v1/trips/{trip['id']}/optimization", headers=header(context[3]))
    assert saved.status_code == 200 and saved.json()["id"] == plan["id"]
    assert approve(context, trip, plan).status_code == 409
    assert approve(context, trip, plan, override=True).status_code == 422
    # Adjust confirmed departure and reoptimize: no manual override of time commitments.
    corrected = (datetime.fromisoformat(departure) - timedelta(hours=1)).isoformat()
    retry = optimize(context, trip, corrected)
    assert retry.status_code == 200, retry.text
    assert approve(context, trip, retry.json()).status_code == 200


def test_stale_policy_latest_plan_and_cancelled_stop_block_approval(context, monkeypatch):
    trip, departure = route_trip(context)
    plan = optimize(context, trip, departure).json()
    monkeypatch.setattr(get_settings(), "fixed_time_tolerance_seconds", 1200)
    assert approve(context, trip, plan).status_code == 409
    assert (
        context[0]
        .get(f"/api/v1/trips/{trip['id']}/optimization", headers=header(context[3]))
        .json()["stale"]
    )
    fresh = optimize(context, trip, departure).json()
    assert approve(context, trip, plan).status_code == 409
    cancelled = context[0].post(
        f"/api/v1/deliveries/{trip['stops'][0]['delivery_id']}/status",
        headers=header(context[3]),
        json={"from_status": "PLANNED", "to_status": "CANCELLED", "reason": "Test stale routing"},
    )
    assert cancelled.status_code == 200
    assert approve(context, trip, fresh).status_code == 409


def test_departure_role_service_validation_and_real_provider_failure(context, monkeypatch):
    trip, departure = route_trip(context)
    client, engine, _, tokens = context
    path = f"/api/v1/trips/{trip['id']}/optimize"
    assert client.post(path, headers=header(tokens), json={}).status_code == 422
    assert (
        client.post(
            path, headers=header(tokens, "DRIVER"), json={"planned_departure_at": departure}
        ).status_code
        == 403
    )
    assert optimize(context, trip, departure, service_seconds={str(uuid4()): 0}).status_code == 422
    assert (
        optimize(context, trip, departure, service_seconds={trip["stops"][0]["id"]: -1}).status_code
        == 422
    )
    monkeypatch.setattr(get_settings(), "osrm_url", "http://127.0.0.1:1")
    failed = optimize(context, trip, departure)
    assert failed.status_code == 503 and "không fallback" in failed.json()["detail"]
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM trip_route_plans WHERE trip_id=:id"), {"id": trip["id"]}
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT planned_departure_at FROM trips WHERE id=:id"), {"id": trip["id"]}
            )
            is None
        )
