from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_m1_api import context as context
from test_m1_api import header
from test_m8_reporting_policy import history

from app.database import table

pytestmark = pytest.mark.integration


def setup_attempt(ctx, seconds=0):
    row, plans, events, audits = history(seconds=seconds)
    client, engine, records, tokens = ctx
    vehicle = client.post(
        "/api/v1/vehicles", headers=header(tokens), json={"plate_no": "R8-" + uuid4().hex[:12]}
    ).json()
    vid = UUID(vehicle["id"])
    row["vehicle_id"] = vid
    actor = records["ADMIN"]["id"]
    with engine.begin() as db:
        db.execute(
            table("deliveries", db)
            .insert()
            .values(
                id=row["delivery_id"],
                code=uuid4().hex,
                recipient_name="Private customer",
                recipient_phone="0901234567",
                address_text="Private address",
                commitment_type="FIXED_TIME",
                appointment_at=row["arrived_at"],
            )
        )
        db.execute(
            table("trips", db)
            .insert()
            .values(
                id=row["trip_id"],
                trip_date=row["trip_date"],
                vehicle_id=vid,
                created_at=row["trip_created_at"],
                created_by=actor,
            )
        )
        db.execute(
            table("trip_stops", db)
            .insert()
            .values(
                id=row["attempt_id"],
                trip_id=row["trip_id"],
                delivery_id=row["delivery_id"],
                sequence_no=1,
                arrived_at=row["arrived_at"],
                status="FAILED",
                completed_at=row["completed_at"],
            )
        )
        db.execute(
            table("trip_route_plans", db)
            .insert()
            .values(
                **plans[0],
                input_fingerprint="history-fixture",
                result_json={},
                approved_at=row["trip_created_at"],
                approved_by=actor,
                created_by=actor,
            )
        )
        events[0]["actor_user_id"] = actor
        db.execute(table("delivery_status_events", db).insert().values(**events[0]))
        audits[0].update(actor_user_id=actor, resource_type="delivery")
        db.execute(table("audit_logs", db).insert().values(**audits[0]))
    return row, dict(date_from=row["trip_date"], date_to=row["trip_date"], vehicle_id=str(vid))


def test_reporting_real_history_early_trace_rbac_and_no_public_data(context):
    client, _, _, tokens = context
    row, params = setup_attempt(context, -901)
    for endpoint in [
        "summary",
        "attempts",
        "financial",
        "financial/sources",
        "vehicles",
        f"vehicles/{row['vehicle_id']}/intervals",
    ]:
        url = "/api/v1/reports/" + endpoint
        assert client.get(url, params=params).status_code == 401
        for denied in ("DISPATCHER", "DRIVER"):
            assert client.get(url, params=params, headers=header(tokens, denied)).status_code == 403
        response = client.get(url, params=params, headers=header(tokens))
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert "Private customer" not in response.text
        assert "0901234567" not in response.text
        assert "Private address" not in response.text
    summary = client.get("/api/v1/reports/summary", params=params, headers=header(tokens)).json()
    assert summary["early"] == summary["eligible_attempts"] == summary["failed_attempts"] == 1
    assert summary["early_rate"] == "1"
    assert summary["on_time_rate"] == "0"
    attempt = client.get("/api/v1/reports/attempts", params=params, headers=header(tokens)).json()[
        "items"
    ][0]
    assert attempt["status"] == "EARLY"
    assert attempt["arrival_event_id"] and attempt["arrival_audit_id"]
    assert attempt["commitment"]["tolerance_seconds"] == 900


def test_reporting_finance_uses_business_dates_void_and_separate_totals(context):
    client, engine, records, tokens = context
    row, params = setup_attempt(context)
    vid = str(row["vehicle_id"])
    at = row["arrived_at"]
    identifiers = []
    for amount, offset in [("100", 0), (None, 0), ("999", 1)]:
        data = dict(
            vehicle_id=vid,
            liters="2",
            amount=amount,
            filled_at=(at + timedelta(days=offset)).isoformat(),
            client_action_id=str(uuid4()),
        )
        response = client.post("/api/v1/fuel/entries", headers=header(tokens), json=data)
        assert response.status_code == 201, response.text
        identifiers.append(response.json()["id"])
    with engine.begin() as db:
        fuel = table("fuel_entries", db)
        db.execute(fuel.update().where(fuel.c.id == UUID(identifiers[0])).values(deleted_at=at))
        db.execute(
            table("expenses", db)
            .insert()
            .values(
                trip_id=row["trip_id"],
                type="OTHER",
                amount=25,
                incurred_at=at + timedelta(days=5),
                created_by=records["DISPATCHER"]["id"],
            )
        )
    response = client.get("/api/v1/reports/financial", params=params, headers=header(tokens))
    assert response.status_code == 200, response.text
    data = response.json()
    assert Decimal(data["total_fuel_liters"]) == 2
    assert data["total_fuel_cost"] is None and data["fuel_missing_amount"] == 1
    assert Decimal(data["total_trip_expense"]) == 25  # trip_date, not incurred_at or created_at
    assert data["grand_total"] is None and data["grand_total_reason"]
    sources = client.get(
        "/api/v1/reports/financial/sources", params=params, headers=header(tokens)
    ).json()
    assert sources["total"] == 3
    assert sum(r["exclusion_reason"] == "VOIDED" for r in sources["items"]) == 1
    assert all("receipt" not in r and "object_key" not in r for r in sources["items"])
    with engine.connect() as db:
        assert (
            len(
                list(
                    db.execute(
                        select(table("fuel_entries", db)).where(
                            table("fuel_entries", db).c.vehicle_id == UUID(vid)
                        )
                    )
                )
            )
            == 3
        )


def test_reporting_unknown_pagination_and_invalid_period(context):
    client, engine, _, tokens = context
    row, params = setup_attempt(context)
    with engine.begin() as db:
        plans = table("trip_route_plans", db)
        db.execute(
            plans.update()
            .where(plans.c.trip_id == row["trip_id"])
            .values(input_json={"source": None})
        )
    data = client.get("/api/v1/reports/summary", params=params, headers=header(tokens)).json()
    assert data["unknown"] == 1 and data["eligible_attempts"] == 0
    assert data["on_time_rate"] is None
    result = client.get(
        "/api/v1/reports/attempts",
        params={**params, "offset": 1, "limit": 1},
        headers=header(tokens),
    ).json()
    assert result["total"] == 1 and result["items"] == []
    assert (
        client.get(
            "/api/v1/reports/summary",
            params={**params, "date_to": "2026-10-01"},
            headers=header(tokens),
        ).status_code
        == 422
    )


def test_financial_reconciliation_uses_only_current_final_version(context):
    client, engine, records, tokens = context
    row, params = setup_attempt(context)
    at = row["arrived_at"]
    identifier = uuid4()
    with engine.begin() as db:
        db.execute(
            table("fuel_reconciliations", db)
            .insert()
            .values(
                id=identifier,
                vehicle_id=row["vehicle_id"],
                from_at=at,
                to_at=at + timedelta(hours=1),
                status="FINAL",
                created_by=records["ADMIN"]["id"],
            )
        )
        for version in [1, 2]:
            db.execute(
                table("fuel_reconciliation_versions", db)
                .insert()
                .values(
                    reconciliation_id=identifier,
                    version=version,
                    computed_by=records["ADMIN"]["id"],
                    reason="Historical fixture version",
                    result_json=dict(
                        data_status="COMPLETE",
                        reasons=[],
                        actual_liters=str(2 * version),
                        expected_liters="2",
                        variance_pct=str(100 * (version - 1)),
                        alert_flag=version == 2,
                    ),
                )
            )
    response = client.get("/api/v1/reports/financial", params=params, headers=header(tokens))
    assert response.status_code == 200, response.text
    values = response.json()["reconciliations"]
    assert len(values) == 1 and values[0]["version"] == 2
    assert Decimal(values[0]["actual_liters"]) == 4
    with engine.connect() as db:
        versions = table("fuel_reconciliation_versions", db)
        assert (
            len(
                list(db.execute(select(versions).where(versions.c.reconciliation_id == identifier)))
            )
            == 2
        )


def test_rescheduled_attempts_keep_distinct_snapshot_commitments_and_trip_dates(context):
    from copy import deepcopy

    client, engine, records, tokens = context
    first, params = setup_attempt(context, -901)
    second, plans, events, audits = history("BEFORE_DEADLINE", 1)
    second["delivery_id"] = first["delivery_id"]
    for key in ["arrived_at", "trip_created_at", "completed_at"]:
        second[key] += timedelta(days=1)
    second["trip_date"] = "2026-10-17"
    plan = plans[0]
    source = plan["input_json"]["source"]
    source["trip"]["trip_date"] = second["trip_date"]
    source["stops"][0]["delivery_id"] = str(first["delivery_id"])
    source["stops"][0]["deadline_at"] = (second["arrived_at"] - timedelta(seconds=1)).isoformat()
    actor = records["ADMIN"]["id"]
    with engine.begin() as db:
        db.execute(
            table("trips", db)
            .insert()
            .values(
                id=second["trip_id"],
                trip_date=second["trip_date"],
                vehicle_id=first["vehicle_id"],
                created_at=second["trip_created_at"],
                created_by=actor,
            )
        )
        db.execute(
            table("trip_stops", db)
            .insert()
            .values(
                id=second["attempt_id"],
                trip_id=second["trip_id"],
                delivery_id=first["delivery_id"],
                sequence_no=1,
                arrived_at=second["arrived_at"],
                completed_at=second["completed_at"],
                status="DELIVERED",
            )
        )
        db.execute(
            table("trip_route_plans", db)
            .insert()
            .values(
                **plan,
                input_fingerprint="second-attempt-history",
                result_json={},
                approved_at=second["trip_created_at"],
                approved_by=actor,
                created_by=actor,
            )
        )
        event = deepcopy(events[0])
        event.update(
            delivery_id=first["delivery_id"],
            event_time=second["arrived_at"],
            request_id="second-arrival",
            actor_user_id=actor,
        )
        db.execute(table("delivery_status_events", db).insert().values(**event))
        audit = deepcopy(audits[0])
        audit.update(
            resource_id=str(first["delivery_id"]),
            resource_type="delivery",
            request_id="second-arrival",
            created_at=second["arrived_at"],
            actor_user_id=actor,
        )
        db.execute(table("audit_logs", db).insert().values(**audit))
        deliveries = table("deliveries", db)
        db.execute(
            deliveries.update()
            .where(deliveries.c.id == first["delivery_id"])
            .values(appointment_at=second["arrived_at"] + timedelta(days=100))
        )
    wide = {**params, "date_to": "2026-10-17"}
    result = client.get("/api/v1/reports/summary", params=wide, headers=header(tokens))
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["attempts"] == 2 and data["early"] == data["late"] == 1
    assert data["eligible_attempts"] == 2 and Decimal(data["early_rate"]) == Decimal("0.5")
    single = client.get("/api/v1/reports/summary", params=params, headers=header(tokens)).json()
    assert single["attempts"] == 1 and single["early"] == 1
