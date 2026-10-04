import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL required for mandatory real PostGIS integration tests")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    yield engine
    engine.dispose()


@pytest.mark.integration
def test_baseline_schema_and_postgis(database):
    expected = {
        "users",
        "vehicles",
        "driver_profiles",
        "deliveries",
        "trips",
        "trip_stops",
        "delivery_status_events",
        "pod_photos",
        "tracking_tokens",
        "fuel_profiles",
        "fuel_entries",
        "expenses",
        "maintenance_rules",
        "maintenance_events",
        "vehicle_documents",
        "safety_alerts",
        "audit_logs",
    }
    assert expected <= set(inspect(database).get_table_names())
    with database.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
        assert connection.scalar(text("SELECT PostGIS_Version()"))
        distance = connection.scalar(
            text(
                "SELECT ST_Distance(ST_Point(106.7,10.7)::geography, "
                "ST_Point(106.7,10.7001)::geography)"
            )
        )
        assert 10 < distance < 12


@pytest.mark.integration
def test_invalid_time_window_rejected(database):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO deliveries(code, recipient_name, recipient_phone, address_text,
                commitment_type, window_start, window_end)
            VALUES ('M0-invalid', 'Test', '0900000000', 'Test', 'TIME_WINDOW',
                '2026-10-04 15:00:00+07', '2026-10-04 14:00:00+07')
        """)
        )
