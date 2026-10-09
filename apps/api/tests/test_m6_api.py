from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

import pytest
import test_m1_api
from sqlalchemy import text
from test_m1_api import header
from test_m2_api import command, order
from test_m3_api import approve, optimize, route_trip
from test_m5_api import delivering, payload, photo, upload

from app.config import get_settings
from app.routing_provider import RoutingProvider
from app.tracking_security import token_hash

context = test_m1_api.context
pytestmark = pytest.mark.integration


def planned(ctx):
    # M6 fixtures use broad appointment windows; M3's tight-window solver tests remain intact.
    trip, departure = route_trip(ctx, count=4)
    result = optimize(ctx, trip, departure)
    assert result.status_code == 200, result.text
    assert approve(ctx, trip, result.json()).status_code == 200
    return trip


def started(ctx):
    trip = planned(ctx)
    result = ctx[0].post(f"/api/v1/trips/{trip['id']}/start", headers=header(ctx[3], "DRIVER"))
    assert result.status_code == 200, result.text
    return trip


def link(ctx, stop, role="ADMIN"):
    return ctx[0].post(
        "/api/v1/tracking-links",
        headers=header(ctx[3], role),
        json={"delivery_id": stop["delivery_id"]},
    )


def raw(created):
    assert created.status_code == 201, created.text
    return created.json()["url"].rsplit("/", 1)[-1]


def public(ctx, token):
    return ctx[0].get("/api/v1/public/tracking/" + token)


def snapshot(ctx, trip, age=0, latitude=10.7769, longitude=106.7009):
    now = datetime.now(UTC) - timedelta(seconds=age)
    with ctx[1].begin() as db:
        db.execute(
            text("""INSERT INTO gps_snapshots
            (vehicle_id,traccar_device_id,position_id,latitude,longitude,speed_kmh,course,gps_at,
             server_received_at,backend_received_at,engine_state)
            VALUES (:id,99999,99999,:lat,:lon,0,0,:now,:now,:now,'UNKNOWN')
            ON CONFLICT(vehicle_id) DO UPDATE SET latitude=:lat,longitude=:lon,
              gps_at=:now,server_received_at=:now,backend_received_at=:now"""),
            {"id": trip["vehicle_id"], "lat": latitude, "lon": longitude, "now": now},
        )


def test_scoped_links_hash_only_multiple_rbac_revoke_audit(context):
    trip = planned(context)
    stop = trip["stops"][0]
    assert link(context, stop).status_code == 409
    assert (
        context[0]
        .post(f"/api/v1/trips/{trip['id']}/start", headers=header(context[3], "DRIVER"))
        .status_code
        == 200
    )
    assert link(context, stop, "DRIVER").status_code == 403
    first, second = link(context, stop), link(context, stop, "DISPATCHER")
    a, b = raw(first), raw(second)
    assert a != b
    data = public(context, a)
    assert data.status_code == 200, data.text
    assert set(data.json()) == {
        "code",
        "status",
        "completed_at",
        "expires_at",
        "gps",
        "eta_at",
        "eta_status",
    }
    assert data.json()["expires_at"] is None
    assert data.json()["gps"] is None
    assert data.headers["cache-control"] == "no-store"
    assert data.headers["referrer-policy"] == "no-referrer"
    with context[1].connect() as db:
        stored = (
            db.execute(
                text("SELECT * FROM tracking_tokens WHERE id=:id"), {"id": first.json()["id"]}
            )
            .mappings()
            .one()
        )
        assert stored["token_hash"] == token_hash(a)
        assert stored["trip_stop_id"] == UUID(stop["id"])
        audits = str(
            db.execute(
                text("SELECT after_json FROM audit_logs WHERE resource_id=:id"),
                {"id": first.json()["id"]},
            ).all()
        )
        assert a not in audits and stored["token_hash"] not in audits
    assert (
        context[0].get("/api/v1/deliveries", headers={"Authorization": "Bearer " + a}).status_code
        == 401
    )
    revoke = f"/api/v1/tracking-links/{first.json()['id']}/revoke"
    assert context[0].post(revoke, headers=header(context[3], "DRIVER")).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: context[0].post(revoke, headers=header(context[3])), range(2))
        )
    assert all(r.status_code == 200 for r in results)
    assert results[0].json() == results[1].json()
    assert public(context, a).status_code == 410
    assert public(context, b).status_code == 200
    assert public(context, "invalid").status_code == 410
    assert public(context, "A" * 43).status_code == 410
    with context[1].connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM audit_logs WHERE resource_id=:id AND action='REVOKE'"),
                {"id": first.json()["id"]},
            )
            == 1
        )


def test_exact_vehicle_gps_eta_multistop_cache_and_no_internal_data(context):
    trip = started(context)
    with context[1].connect() as db:
        stop_id = str(
            db.scalar(
                text(
                    "SELECT id FROM trip_stops WHERE trip_id=:id ORDER BY sequence_no DESC LIMIT 1"
                ),
                {"id": trip["id"]},
            )
        )
    stop = next(s for s in trip["stops"] if s["id"] == stop_id)
    token = raw(link(context, stop))
    snapshot(context, trip)
    first = public(context, token)
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["gps"]["latitude"] == 10.7769
    assert data["gps"]["longitude"] == 106.7009
    assert data["eta_status"] == "AVAILABLE"
    with context[1].connect() as db:
        approved = db.scalar(
            text(
                "SELECT result_json FROM trip_route_plans "
                "WHERE trip_id=:id AND approved_at IS NOT NULL"
            ),
            {"id": trip["id"]},
        )["stops"]
    matrix = RoutingProvider(get_settings()).matrix(
        [(10.7769, 106.7009)] + [(s["latitude"], s["longitude"]) for s in approved]
    )
    arrival = datetime.now(UTC)
    for index, detail in enumerate(approved):
        arrival += timedelta(seconds=matrix.durations_s[index][index + 1])
        if detail["window_start"]:
            arrival = max(arrival, datetime.fromisoformat(detail["window_start"]))
        if index < len(approved) - 1:
            arrival += timedelta(seconds=detail["service_seconds"])
    assert abs((datetime.fromisoformat(data["eta_at"]) - arrival).total_seconds()) < 5
    start = monotonic()
    cached = public(context, token)
    assert monotonic() - start < 1
    assert cached.json()["eta_at"] == data["eta_at"]
    samples = []
    for _ in range(20):
        begin = monotonic()
        assert public(context, token).status_code == 200
        samples.append(monotonic() - begin)
    assert sorted(samples)[18] < 1, samples
    for field in (
        "vehicle_id",
        "delivery_id",
        "recipient_name",
        "recipient_phone",
        "address_text",
        "notes",
        "stops",
        "geometry",
        "history",
        "pod",
    ):
        assert field not in data
    other = next(s for s in trip["stops"] if s["id"] != stop_id)
    other_token = raw(link(context, other))
    assert public(context, other_token).json()["code"] != data["code"]
    outsider = (
        context[0]
        .post(
            "/api/v1/vehicles",
            headers=header(context[3]),
            json={"plate_no": "M6-other-" + token[:8]},
        )
        .json()
    )
    snapshot(context, {"vehicle_id": outsider["id"]}, latitude=10.8, longitude=106.8)
    assert public(context, token).json()["gps"]["latitude"] == 10.7769


@pytest.mark.parametrize(
    "age,coords,expected",
    [(40, True, "STALE"), (121, True, "LOST"), (0, False, None), (-60, True, None)],
)
def test_stale_missing_invalid_future_gps_never_fakes_eta(context, age, coords, expected):
    trip = started(context)
    token = raw(link(context, trip["stops"][0]))
    if coords:
        snapshot(context, trip, age)
    data = public(context, token).json()
    assert data["eta_at"] is None and data["eta_status"] == "UNKNOWN"
    if expected:
        assert data["gps"]["freshness"] == expected
    else:
        assert data["gps"] is None


def test_osrm_unavailable_real_failure_no_fallback(context, monkeypatch):
    trip = started(context)
    token = raw(link(context, trip["stops"][0]))
    snapshot(context, trip)
    monkeypatch.setenv("OSRM_URL", "http://127.0.0.1:1")
    get_settings.cache_clear()
    response = public(context, token)
    assert response.status_code == 200
    assert response.json()["gps"]["freshness"] == "NORMAL"
    assert response.json()["eta_at"] is None


def test_real_redis_limits_and_failure_are_closed(context, monkeypatch):
    trip = started(context)
    token = raw(link(context, trip["stops"][0]))
    monkeypatch.setenv("TRACKING_TOKEN_REQUESTS_PER_MINUTE", "3")
    get_settings.cache_clear()
    assert all(public(context, token).status_code == 200 for _ in range(3))
    limited = public(context, token)
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    failure = public(context, token)
    assert failure.status_code == 503 and "gps" not in failure.text


def test_delivered_exact_one_hour_expiry_no_live_gps_and_new_attempt_invalid(context):
    trip = started(context)
    stop = trip["stops"][0]
    token = raw(link(context, stop))
    delivering(context, stop)
    data = photo()
    assert upload(context, stop, data, payload(stop, data)).status_code == 201
    assert (
        command(context, stop["delivery_id"], "DELIVERING", "DELIVERED", "DRIVER").status_code
        == 200
    )
    snapshot(context, trip)
    response = public(context, token)
    assert response.status_code == 200, response.text
    dto = response.json()
    assert (
        command(context, stop["delivery_id"], "DELIVERING", "DELIVERED", "DRIVER").status_code
        == 409
    )
    assert public(context, token).json()["expires_at"] == dto["expires_at"]
    assert dto["gps"] is None and dto["eta_at"] is None and dto["eta_status"] == "COMPLETED"
    assert datetime.fromisoformat(dto["expires_at"]) - datetime.fromisoformat(
        dto["completed_at"]
    ) == timedelta(hours=1)
    with context[1].begin() as db:
        delivered = db.scalar(
            text(
                "SELECT event_time FROM delivery_status_events "
                "WHERE delivery_id=:id AND to_status='DELIVERED'"
            ),
            {"id": stop["delivery_id"]},
        )
        assert datetime.fromisoformat(dto["completed_at"]) == delivered
        db.execute(
            text("UPDATE tracking_tokens SET expires_at=now() WHERE token_hash=:hash"),
            {"hash": token_hash(token)},
        )
    expired = public(context, token)
    assert expired.status_code == 410 and "gps" not in expired.text


def test_failed_revokes_and_assignment_changes_cannot_follow_new_attempt(context):
    trip = started(context)
    stop = trip["stops"][0]
    token = raw(link(context, stop))
    assert command(context, stop["delivery_id"], "EN_ROUTE", "ARRIVED", "DRIVER").status_code == 200
    assert (
        command(
            context, stop["delivery_id"], "ARRIVED", "FAILED", "DRIVER", reason="Customer absent"
        ).status_code
        == 200
    )
    assert public(context, token).status_code == 410
    with context[1].connect() as db:
        assert db.scalar(
            text("SELECT revoked_at FROM tracking_tokens WHERE token_hash=:hash"),
            {"hash": token_hash(token)},
        )
    values = order()
    result = context[0].post(
        f"/api/v1/deliveries/{stop['delivery_id']}/reschedule",
        headers=header(context[3], "DISPATCHER"),
        json={
            "commitment": {
                k: values[k] for k in ("commitment_type", "scheduled_date", "appointment_at")
            }
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["delivery"]["status"] == "RESCHEDULED"
    new_trip = context[0].post(
        "/api/v1/trips",
        headers=header(context[3]),
        json={
            "trip_date": values["scheduled_date"],
            "vehicle_id": trip["vehicle_id"],
            "driver_id": trip["driver_id"],
            "delivery_ids": [stop["delivery_id"]],
            "start": trip["start"],
            "end": trip["end"],
        },
    )
    assert new_trip.status_code == 201, new_trip.text
    assert public(context, token).status_code == 410
    second = trip["stops"][1]
    old = raw(link(context, second))
    with context[1].begin() as db:
        db.execute(text("UPDATE trips SET vehicle_id=NULL WHERE id=:id"), {"id": trip["id"]})
    assert public(context, old).status_code == 410
