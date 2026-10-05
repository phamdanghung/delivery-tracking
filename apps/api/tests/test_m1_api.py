import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from app.auth import hasher
from app.config import get_settings
from app.database import table
from app.gps import ingest
from app.main import app
from app.traccar import Traccar


@pytest.fixture
def context(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    assert url, "Real database is mandatory"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "m1-isolated-test-key-with-more-than-32-characters")
    get_settings.cache_clear()
    engine = create_engine(url)
    records = {}
    with engine.begin() as db:
        users = table("users", db)
        for role in ("ADMIN", "DISPATCHER", "DRIVER"):
            email = uuid4().hex + "@test.local"
            row = (
                db.execute(
                    users.insert()
                    .values(
                        full_name="Test " + role,
                        email=email,
                        password_hash=hasher.hash("M1-test-password-long"),
                        role=role,
                    )
                    .returning(users)
                )
                .mappings()
                .one()
            )
            records[role] = dict(row)
    with TestClient(app) as client:
        tokens = {}
        for role, row in records.items():
            response = client.post(
                "/api/v1/auth/login",
                json={"email": row["email"], "password": "M1-test-password-long"},
            )
            assert response.status_code == 200, response.text
            tokens[role] = response.json()
        yield client, engine, records, tokens
    # The enclosing database is isolated and discarded by the verification harness.
    with engine.begin() as db:
        db.execute(text("UPDATE users SET is_active=false WHERE email LIKE '%@test.local'"))
    engine.dispose()
    get_settings.cache_clear()


def header(tokens, role="ADMIN"):
    return {"Authorization": "Bearer " + tokens[role]["access_token"]}


def test_login_errors_user_role_scope_and_no_password_leak(context):
    client, engine, records, tokens = context
    response = client.post(
        "/api/v1/auth/login", json={"email": records["ADMIN"]["email"], "password": "wrong"}
    )
    assert response.status_code == 401
    assert client.get("/api/v1/vehicles").status_code == 401
    assert client.get("/api/v1/vehicles", headers=header(tokens, "DRIVER")).status_code == 403
    assert client.get("/api/v1/users", headers=header(tokens, "DISPATCHER")).status_code == 403
    assert (
        client.post(
            "/api/v1/vehicles", headers=header(tokens, "DISPATCHER"), json={"plate_no": "X"}
        ).status_code
        == 403
    )
    response = client.get("/api/v1/auth/me", headers=header(tokens, "DRIVER"))
    assert response.json()["id"] == str(records["DRIVER"]["id"])
    assert "password" not in response.text
    assert records["ADMIN"]["password_hash"].startswith("$argon2id$")


def test_refresh_rotation_replay_revokes_family(context):
    client, _, _, tokens = context
    old = tokens["ADMIN"]
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert response.status_code == 200
    new = response.json()
    assert new["refresh_token"] != old["refresh_token"]
    assert client.get("/api/v1/auth/me", headers=header({"ADMIN": old})).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/auth/me", headers=header({"ADMIN": new})).status_code == 401


def test_user_driver_link_active_revocation_and_audit(context):
    client, engine, _, tokens = context
    email = uuid4().hex + "@test.local"
    response = client.post(
        "/api/v1/users",
        headers=header(tokens),
        json={
            "full_name": "Driver",
            "email": email,
            "password": "M1-new-driver-password",
            "role": "DRIVER",
            "phone": "0900000000",
        },
    )
    assert response.status_code == 201
    user = response.json()
    drivers = client.get("/api/v1/drivers", headers=header(tokens, "DISPATCHER")).json()
    assert any(item["user_id"] == user["id"] for item in drivers)
    logged = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "M1-new-driver-password"}
    ).json()
    assert (
        client.patch(
            "/api/v1/users/" + user["id"], headers=header(tokens), json={"is_active": False}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=header({"ADMIN": logged})).status_code == 401
    with engine.connect() as db:
        logs = db.execute(select(table("audit_logs", db))).mappings().all()
        assert any(
            item["resource_id"] == user["id"] and item["action"] == "UPDATE" for item in logs
        )
        assert all("password" not in str(item["after_json"]) for item in logs)


def test_last_admin_cannot_be_disabled(context):
    client, _, records, tokens = context
    response = client.patch(
        "/api/v1/users/" + str(records["ADMIN"]["id"]),
        headers=header(tokens),
        json={"is_active": False},
    )
    assert response.status_code == 409


def test_driver_profile_vehicle_relation_is_read_only_through_trip(context):
    client, engine, records, tokens = context
    with engine.begin() as db:
        profiles, vehicles, trips = (
            table("driver_profiles", db),
            table("vehicles", db),
            table("trips", db),
        )
        driver_id = db.scalar(
            profiles.insert().values(user_id=records["DRIVER"]["id"]).returning(profiles.c.id)
        )
        vehicle_id = db.scalar(
            vehicles.insert().values(plate_no="REL-" + uuid4().hex[:8]).returning(vehicles.c.id)
        )
        trip_id = db.scalar(
            trips.insert()
            .values(driver_id=driver_id, vehicle_id=vehicle_id, trip_date=datetime.now(UTC).date())
            .returning(trips.c.id)
        )
    response = client.get("/api/v1/drivers", headers=header(tokens, "DISPATCHER"))
    assert response.status_code == 200
    profile = next(item for item in response.json() if item["id"] == str(driver_id))
    assert profile["user_id"] == str(records["DRIVER"]["id"])
    assert profile["vehicle_assignments"][0]["trip_id"] == str(trip_id)
    assert profile["vehicle_assignments"][0]["vehicle_id"] == str(vehicle_id)
    data = {"user_id": str(records["DRIVER"]["id"]), "active": False}
    assert (
        client.put(
            f"/api/v1/drivers/{driver_id}", headers=header(tokens, "DISPATCHER"), json=data
        ).status_code
        == 403
    )
    assert (
        client.put(f"/api/v1/drivers/{driver_id}", headers=header(tokens), json=data).json()[
            "active"
        ]
        is False
    )
    assert client.get("/api/v1/drivers", headers=header(tokens, "DRIVER")).status_code == 403
    # M2 now exposes draft creation; incomplete input must not create/publish a trip.
    assert client.post("/api/v1/trips", headers=header(tokens), json={}).status_code == 422


def test_vehicle_mapping_ingest_duplicate_out_of_order_remap_and_outage(context, monkeypatch):
    client, engine, _, tokens = context
    monkeypatch.setattr(Traccar, "device_exists", lambda self, device: device in (123, 124))
    data = {"plate_no": "M1-" + uuid4().hex[:8], "traccar_device_id": 123}
    response = client.post("/api/v1/vehicles", headers=header(tokens), json=data)
    assert response.status_code == 201
    identifier = response.json()["id"]
    assert (
        client.post(
            "/api/v1/vehicles", headers=header(tokens), json={**data, "plate_no": "Other"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/vehicles",
            headers=header(tokens),
            json={"plate_no": "Bad", "traccar_device_id": 999},
        ).status_code
        == 422
    )
    now = datetime.now(UTC)
    raw = {
        "id": 1234,
        "deviceId": 123,
        "latitude": 10.7,
        "longitude": 106.7,
        "valid": True,
        "speed": 10,
        "course": 90,
        "fixTime": now.isoformat(),
        "serverTime": now.isoformat(),
        "attributes": {"ignition": True},
    }
    with engine.begin() as db:
        assert ingest(db, raw)
        assert not ingest(db, raw)
        assert not ingest(
            db, {**raw, "id": 1233, "fixTime": (now - timedelta(seconds=1)).isoformat()}
        )
        snapshot = db.execute(select(table("gps_snapshots", db))).mappings().one()
        assert str(snapshot["vehicle_id"]) == identifier
        assert snapshot["engine_state"] == "MOVING"
    monkeypatch.setattr(Traccar, "get", lambda self, endpoint, params=None: [raw])
    assert (
        client.get(f"/api/v1/vehicles/{identifier}/live", headers=header(tokens)).json()[
            "freshness"
        ]
        == "NORMAL"
    )
    response = client.put(
        f"/api/v1/vehicles/{identifier}",
        headers=header(tokens),
        json={**data, "traccar_device_id": 124},
    )
    assert response.status_code == 200
    with engine.connect() as db:
        assert db.execute(select(table("gps_snapshots", db))).first() is None

    def offline(*args, **kwargs):
        raise HTTPException(503, "Traccar không phản hồi")

    monkeypatch.setattr(Traccar, "get", offline)
    assert (
        client.get(f"/api/v1/vehicles/{identifier}/live", headers=header(tokens)).status_code == 503
    )
    assert (
        client.delete(f"/api/v1/vehicles/{identifier}", headers=header(tokens)).status_code == 204
    )
