from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import test_m1_api
from sqlalchemy import text
from test_m1_api import header

from app.config import get_settings

context = test_m1_api.context


def order(kind="FIXED_TIME", **changes):
    when = datetime.now(UTC) + timedelta(days=2)
    times = {
        "FIXED_TIME": {"appointment_at": when.isoformat()},
        "TIME_WINDOW": {
            "window_start": when.isoformat(),
            "window_end": (when + timedelta(hours=1)).isoformat(),
        },
        "BEFORE_DEADLINE": {"deadline_at": when.isoformat()},
    }
    return {
        "recipient_name": "M2 test",
        "recipient_phone": "0900000000",
        "address_text": "Địa chỉ mô phỏng",
        "latitude": 10.7,
        "longitude": 106.7,
        "commitment_type": kind,
        "scheduled_date": when.date().isoformat(),
        "weight_kg": 20,
        "volume_m3": 2,
        **times[kind],
        **changes,
    }


def create(ctx, **changes):
    client, _, _, tokens = ctx
    result = client.post(
        "/api/v1/deliveries", headers=header(tokens, "DISPATCHER"), json=order(**changes)
    )
    assert result.status_code == 201, result.text
    return result.json()


def fleet(ctx):
    client, engine, users, tokens = ctx
    vehicle = client.post(
        "/api/v1/vehicles",
        headers=header(tokens),
        json={"plate_no": uuid4().hex, "max_weight_kg": 10, "max_volume_m3": 1},
    ).json()
    with engine.begin() as db:
        profile = db.scalar(
            text("INSERT INTO driver_profiles(user_id) VALUES (:user) RETURNING id"),
            {"user": users["DRIVER"]["id"]},
        )
    return vehicle["id"], str(profile)


def draft(ctx, identifiers, **changes):
    vehicle, driver = fleet(ctx)
    return {
        "trip_date": order()["scheduled_date"],
        "vehicle_id": vehicle,
        "driver_id": driver,
        "delivery_ids": identifiers,
        "start": {"latitude": 10.8, "longitude": 106.8},
        "end": {"latitude": 10.8, "longitude": 106.8},
        **changes,
    }


def command(ctx, identifier, old, new, role="DISPATCHER", **changes):
    return ctx[0].post(
        f"/api/v1/deliveries/{identifier}/status",
        headers=header(ctx[3], role),
        json={"from_status": old, "to_status": new, **changes},
    )


@pytest.mark.integration
def test_seven_orders_three_commitments_draft_overload_and_no_approval(context):
    client, engine, _, tokens = context
    items = [
        create(context, kind=kind)
        for kind in [
            "FIXED_TIME",
            "TIME_WINDOW",
            "BEFORE_DEADLINE",
            "FIXED_TIME",
            "TIME_WINDOW",
            "BEFORE_DEADLINE",
            "FIXED_TIME",
        ]
    ]
    data = draft(context, [x["id"] for x in items])
    response = client.post("/api/v1/trips", headers=header(tokens, "DISPATCHER"), json=data)
    assert response.status_code == 201, response.text
    trip = response.json()
    assert trip["status"] == "DRAFT" and len(trip["stops"]) == 7
    assert trip["weight_kg"] == 140 and trip["volume_m3"] == 14
    assert len(trip["warnings"]) == 2
    assert [x["delivery_id"] for x in trip["stops"]] == data["delivery_ids"]
    assert all(x["status"] == "PLANNED" and x["eta_at"] is None for x in trip["stops"])
    assert (
        client.post(f"/api/v1/trips/{trip['id']}/start", headers=header(tokens)).status_code == 409
    )
    assert command(context, items[0]["id"], "PLANNED", "ASSIGNED").status_code == 409
    assert client.post("/api/v1/trips", headers=header(tokens), json=data).status_code == 409
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM delivery_status_events WHERE delivery_id=:id"),
                {"id": items[0]["id"]},
            )
            == 2
        )


@pytest.mark.integration
def test_config_missing_and_override_and_environment(context, monkeypatch):
    client, _, _, tokens = context
    monkeypatch.delenv("COMPANY_LATITUDE", raising=False)
    monkeypatch.delenv("COMPANY_LONGITUDE", raising=False)
    get_settings.cache_clear()
    assert not client.get("/api/v1/trips/config", headers=header(tokens)).json()["configured"]
    item = create(context)
    data = draft(context, [item["id"]], start=None, end=None)
    assert client.post("/api/v1/trips", headers=header(tokens), json=data).status_code == 422
    monkeypatch.setenv("COMPANY_LATITUDE", "10.9")
    monkeypatch.setenv("COMPANY_LONGITUDE", "106.9")
    get_settings.cache_clear()
    result = client.post("/api/v1/trips", headers=header(tokens), json=data)
    assert result.status_code == 201, result.text
    assert result.json()["start"] == {"latitude": 10.9, "longitude": 106.9}
    assert result.json()["end"] == result.json()["start"]


@pytest.mark.integration
def test_validation_edit_filter_and_roles(context):
    client, _, _, tokens = context
    for changes in [
        {"recipient_phone": ""},
        {"weight_kg": -1},
        {"latitude": 91},
        {"longitude": None},
        {"appointment_at": None},
        {"appointment_at": "2026-10-10T12:00:00"},
    ]:
        assert (
            client.post(
                "/api/v1/deliveries", headers=header(tokens), json=order(**changes)
            ).status_code
            == 422
        )
    bad = order(kind="TIME_WINDOW", window_end="2020-01-01T00:00:00+07:00")
    assert client.post("/api/v1/deliveries", headers=header(tokens), json=bad).status_code == 422
    assert (
        client.post(
            "/api/v1/deliveries", headers=header(tokens, "DRIVER"), json=order()
        ).status_code
        == 403
    )
    item = create(context)
    assert client.get("/api/v1/deliveries", headers=header(tokens, "DRIVER")).status_code == 403
    assert (
        client.get(f"/api/v1/deliveries/{item['id']}", headers=header(tokens, "DRIVER")).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/deliveries/{item['id']}",
            headers=header(tokens),
            json=order(recipient_name="Edited"),
        ).status_code
        == 200
    )
    rows = client.get(
        "/api/v1/deliveries",
        headers=header(tokens),
        params={"search": item["code"], "status": "CREATED"},
    ).json()
    assert len(rows) == 1 and rows[0]["recipient_name"] == "Edited"
    trip = client.post(
        "/api/v1/trips", headers=header(tokens), json=draft(context, [item["id"]])
    ).json()
    assert (
        client.put(
            f"/api/v1/deliveries/{item['id']}", headers=header(tokens), json=order()
        ).status_code
        == 409
    )
    assert (
        client.get(f"/api/v1/trips/{trip['id']}", headers=header(tokens, "DRIVER")).status_code
        == 403
    )
    assert client.get("/api/v1/trips", headers=header(tokens, "DRIVER")).json() == []


@pytest.mark.integration
@pytest.mark.parametrize("state", ["CREATED", "PLANNED", "ASSIGNED"])
def test_cancel_permissions_reason_audit_and_stale_command(context, state):
    client, engine, _, tokens = context
    item = create(context)
    trip = client.post(
        "/api/v1/trips", headers=header(tokens), json=draft(context, [item["id"]])
    ).json()
    # Explicit test fixture for each permitted state; never promote production DRAFT.
    with engine.begin() as db:
        db.execute(
            text("UPDATE deliveries SET status=CAST(:status AS delivery_status) WHERE id=:id"),
            {"status": state, "id": item["id"]},
        )
        db.execute(
            text("UPDATE trip_stops SET status=CAST(:status AS delivery_status) WHERE trip_id=:id"),
            {"status": state, "id": trip["id"]},
        )
    assert command(context, item["id"], state, "CANCELLED", "DRIVER", reason="x").status_code == 403
    assert command(context, item["id"], state, "CANCELLED").status_code == 422
    assert command(context, item["id"], state, "CANCELLED", reason="Khách hủy").status_code == 200
    assert command(context, item["id"], state, "CANCELLED", reason="Khách hủy").status_code == 409
    detail = client.get(f"/api/v1/deliveries/{item['id']}", headers=header(tokens)).json()
    assert detail["events"][-1]["to_status"] == "CANCELLED"
    assert detail["events"][-1]["reason"] == "Khách hủy"
    assert detail["audit"][-1]["reason"] == "Khách hủy"
    assert detail["audit"][-1]["request_id"]


def approved_fixture(ctx):
    client, engine, _, tokens = ctx
    item = create(ctx)
    trip = client.post(
        "/api/v1/trips", headers=header(tokens), json=draft(ctx, [item["id"]])
    ).json()
    with engine.begin() as db:
        db.execute(text("UPDATE trips SET status='PLANNED' WHERE id=:id"), {"id": trip["id"]})
        db.execute(text("UPDATE deliveries SET status='ASSIGNED' WHERE id=:id"), {"id": item["id"]})
        db.execute(
            text("UPDATE trip_stops SET status='ASSIGNED' WHERE trip_id=:id"), {"id": trip["id"]}
        )
    result = client.post(f"/api/v1/trips/{trip['id']}/start", headers=header(tokens, "DRIVER"))
    assert result.status_code == 200, result.text
    return item, trip


@pytest.mark.integration
def test_forward_state_pod_guard_failed_proposal_confirmation_and_requeue(context):
    client, engine, _, tokens = context
    item, trip = approved_fixture(context)
    identifier = item["id"]
    assert command(context, identifier, "EN_ROUTE", "DELIVERED", "DRIVER").status_code == 409
    assert command(context, identifier, "EN_ROUTE", "ARRIVED", "DRIVER").status_code == 200
    assert (
        command(context, identifier, "ARRIVED", "EN_ROUTE", "DRIVER", reason="GPS sai").status_code
        == 409
    )
    assert command(context, identifier, "ARRIVED", "DELIVERING", "DRIVER").status_code == 200
    assert command(context, identifier, "DELIVERING", "DELIVERED", "DRIVER").status_code == 409
    assert command(context, identifier, "DELIVERING", "FAILED", "DRIVER").status_code == 422
    assert (
        command(
            context, identifier, "DELIVERING", "FAILED", "DRIVER", reason="Khách vắng"
        ).status_code
        == 200
    )
    values = order()
    commitment = {
        key: values[key] for key in ["commitment_type", "scheduled_date", "appointment_at"]
    }
    response = client.post(
        f"/api/v1/deliveries/{identifier}/reschedule",
        headers=header(tokens, "DRIVER"),
        json={"commitment": commitment},
    )
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert not proposal["confirmed"] and proposal["delivery"]["status"] == "FAILED"
    assert (
        client.post(
            f"/api/v1/deliveries/{identifier}/reschedule",
            headers=header(tokens, "DRIVER"),
            json={"proposal_id": proposal["proposal_id"]},
        ).status_code
        == 403
    )
    result = client.post(
        f"/api/v1/deliveries/{identifier}/reschedule",
        headers=header(tokens, "DISPATCHER"),
        json={"proposal_id": proposal["proposal_id"]},
    )
    assert result.status_code == 200, result.text
    assert result.json()["delivery"]["status"] == "RESCHEDULED"
    assert (
        client.post(
            f"/api/v1/deliveries/{identifier}/reschedule",
            headers=header(tokens),
            json={"proposal_id": proposal["proposal_id"]},
        ).status_code
        == 409
    )
    data = {
        "trip_date": values["scheduled_date"],
        "vehicle_id": trip["vehicle_id"],
        "driver_id": trip["driver_id"],
        "delivery_ids": [identifier],
        "start": trip["start"],
        "end": trip["end"],
    }
    assert client.post("/api/v1/trips", headers=header(tokens), json=data).status_code == 201
    with engine.connect() as db:
        assert (
            db.scalar(text("SELECT status FROM trip_stops WHERE trip_id=:id"), {"id": trip["id"]})
            == "FAILED"
        )


@pytest.mark.integration
def test_concurrent_draft_assignment_single_winner(context):
    client, _, _, tokens = context
    item = create(context)
    data = draft(context, [item["id"]])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: (
                    client.post("/api/v1/trips", headers=header(tokens), json=data).status_code
                ),
                range(2),
            )
        )
    assert sorted(results) == [201, 409]


@pytest.mark.integration
def test_past_redelivery_rejected_and_inactive_driver_vehicle(context):
    client, engine, _, tokens = context
    item, trip = approved_fixture(context)
    assert command(context, item["id"], "EN_ROUTE", "ARRIVED", "DRIVER").status_code == 200
    assert (
        command(context, item["id"], "ARRIVED", "FAILED", "DRIVER", reason="Vắng").status_code
        == 200
    )
    commitment = {
        "commitment_type": "FIXED_TIME",
        "scheduled_date": "2020-01-01",
        "appointment_at": "2020-01-01T00:00:00+07:00",
    }
    assert (
        client.post(
            f"/api/v1/deliveries/{item['id']}/reschedule",
            headers=header(tokens),
            json={"commitment": commitment},
        ).status_code
        == 422
    )
    other = create(context)
    data = {
        "trip_date": order()["scheduled_date"],
        "vehicle_id": trip["vehicle_id"],
        "driver_id": trip["driver_id"],
        "delivery_ids": [other["id"]],
        "start": trip["start"],
        "end": trip["end"],
    }
    with engine.begin() as db:
        db.execute(
            text("UPDATE driver_profiles SET active=false WHERE id=:id"), {"id": trip["driver_id"]}
        )
    assert client.post("/api/v1/trips", headers=header(tokens), json=data).status_code == 422

    with engine.begin() as db:
        db.execute(
            text("UPDATE driver_profiles SET active=true WHERE id=:id"), {"id": trip["driver_id"]}
        )
        db.execute(
            text("UPDATE vehicles SET status='INACTIVE' WHERE id=:id"), {"id": trip["vehicle_id"]}
        )
    assert client.post("/api/v1/trips", headers=header(tokens), json=data).status_code == 422


@pytest.mark.integration
def test_other_driver_cannot_read_or_mutate_assigned_delivery(context):
    client, _, _, tokens = context
    item, trip = approved_fixture(context)
    email = uuid4().hex + "@test.local"
    response = client.post(
        "/api/v1/users",
        headers=header(tokens),
        json={
            "full_name": "Other driver",
            "email": email,
            "password": "M2-other-driver-long-password",
            "role": "DRIVER",
        },
    )
    assert response.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "M2-other-driver-long-password"}
    ).json()
    other = {"Authorization": "Bearer " + login["access_token"]}
    assert client.get(f"/api/v1/trips/{trip['id']}", headers=other).status_code == 403
    assert client.get(f"/api/v1/deliveries/{item['id']}", headers=other).status_code == 403
    assert (
        client.post(
            f"/api/v1/deliveries/{item['id']}/status",
            headers=other,
            json={"from_status": "EN_ROUTE", "to_status": "ARRIVED"},
        ).status_code
        == 403
    )
