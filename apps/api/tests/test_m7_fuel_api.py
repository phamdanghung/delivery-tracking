from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_m1_api import context as context
from test_m1_api import header

pytestmark = pytest.mark.integration


def vehicle(ctx):
    response = ctx[0].post(
        "/api/v1/vehicles", headers=header(ctx[3]), json={"plate_no": "M7-" + uuid4().hex[:12]}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_entry_survives_missing_data_versions_keep_history_rbac_and_audit(context):
    client, engine, _, tokens = context
    vid = vehicle(context)
    start = datetime.now(UTC) - timedelta(days=2)
    entry = {
        "vehicle_id": vid,
        "liters": "4.5",
        "amount": "100000",
        "filled_at": start.isoformat(),
        "client_action_id": str(uuid4()),
    }
    assert (
        client.post(
            "/api/v1/fuel/entries", headers=header(tokens, "DRIVER"), json=entry
        ).status_code
        == 403
    )
    created = client.post("/api/v1/fuel/entries", headers=header(tokens, "DISPATCHER"), json=entry)
    assert created.status_code == 201, created.text
    period = {
        "vehicle_id": vid,
        "from_at": start.isoformat(),
        "to_at": (start + timedelta(days=1)).isoformat(),
    }
    response = client.post(
        "/api/v1/fuel/reconciliations", headers=header(tokens, "DISPATCHER"), json=period
    )
    assert response.status_code == 201, response.text
    data = response.json()
    first = data["versions"][0]
    assert first["result_json"]["data_status"] == "INSUFFICIENT"
    assert first["result_json"]["variance_pct"] is None
    assert first["result_json"]["alert_flag"] is False
    assert first["result_json"]["actual_liters"] == "4.500"
    assert client.get("/api/v1/fuel/entries", headers=header(tokens, "DRIVER")).status_code == 403
    assert (
        client.patch(
            "/api/v1/fuel/entries/" + created.json()["id"],
            headers=header(tokens),
            json={**entry, "liters": "5", "reason": "Sửa nhập nhầm"},
        ).status_code
        == 200
    )
    recomputed = client.post(
        f"/api/v1/fuel/reconciliations/{data['id']}/recompute",
        headers=header(tokens),
        json={"reason": "Cập nhật lần đổ"},
    )
    assert recomputed.status_code == 200, recomputed.text
    versions = recomputed.json()["versions"]
    assert versions[0] == first
    assert versions[1]["result_json"]["actual_liters"] == "5.000"
    assert versions[1]["version"] == 2
    with engine.connect() as db:
        actions = (
            db.execute(
                text("SELECT action FROM audit_logs WHERE resource_id=:id"), {"id": data["id"]}
            )
            .scalars()
            .all()
        )
        assert actions == ["CREATE", "RECOMPUTE"]


def test_database_guards_profile_overlap_final_period_overlap_and_timezone(context):
    client, _, _, tokens = context
    vid = vehicle(context)
    profile = {
        "vehicle_id": vid,
        "driving_l_per_100km": "8",
        "idling_l_per_hour": "1",
        "effective_from": "2026-10-01",
        "effective_to": "2026-10-15",
    }
    assert (
        client.post(
            "/api/v1/fuel/profiles", headers=header(tokens, "DISPATCHER"), json=profile
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/fuel/profiles", headers=header(tokens), json=profile).status_code
        == 201
    )
    assert (
        client.post("/api/v1/fuel/profiles", headers=header(tokens), json=profile).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/fuel/profiles",
            headers=header(tokens),
            json={**profile, "effective_from": "2026-10-15", "effective_to": None},
        ).status_code
        == 201
    )
    period = {
        "vehicle_id": vid,
        "from_at": "2026-10-10T08:00:00+07:00",
        "to_at": "2026-10-10T09:00:00+07:00",
    }
    assert (
        client.post(
            "/api/v1/fuel/reconciliations",
            headers=header(tokens),
            json={**period, "from_at": "2026-10-10T08:00:00"},
        ).status_code
        == 422
    )
    drafts = [
        client.post("/api/v1/fuel/reconciliations", headers=header(tokens), json=period)
        for _ in range(2)
    ]
    assert all(d.status_code == 201 for d in drafts)

    def finalize(d):
        return client.post(
            f"/api/v1/fuel/reconciliations/{d.json()['id']}/finalize",
            headers=header(tokens),
            json={"reason": "Chốt kỳ"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(finalize, drafts))
    assert sorted(r.status_code for r in outcomes) == [200, 409]
    data = next(r.json() for r in outcomes if r.status_code == 200)
    assert data["status"] == "FINAL"
    assert data["versions"][-1]["result_json"]["variance_pct"] is None
    # Half-open periods permit a new adjacent FINAL, with no entry double count.
    adjacent = client.post(
        "/api/v1/fuel/reconciliations",
        headers=header(tokens),
        json={**period, "from_at": period["to_at"], "to_at": "2026-10-10T10:00:00+07:00"},
    )
    assert adjacent.status_code == 201
    assert finalize(adjacent).status_code == 200
