import os
from datetime import datetime, time, timedelta
from decimal import Decimal
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest
from test_m1_api import context as context
from test_m1_api import header

from app.config import get_settings
from app.operations_policy import LOCAL
from app.traccar import Traccar

pytestmark = pytest.mark.integration


def test_real_traccar_multi_profile_idle_refill_totals_and_signed_warning(context):
    client, _, _, tokens = context
    settings = get_settings()
    unique = "M7TEST-" + uuid4().hex
    base = settings.traccar_url.rstrip("/")
    with httpx.Client(
        timeout=20,
        trust_env=False,
        auth=(settings.traccar_email, settings.traccar_password.get_secret_value()),
    ) as traccar:
        device = None
        try:
            response = traccar.post(
                base + "/api/devices",
                json={"name": "M7 SIMULATED integration only", "uniqueId": unique},
            )
            assert response.status_code == 200, response.text
            device = response.json()
            vehicle = client.post(
                "/api/v1/vehicles",
                headers=header(tokens),
                json={"plate_no": unique[:24], "traccar_device_id": device["id"]},
            )
            assert vehicle.status_code == 201, vehicle.text
            vid = vehicle.json()["id"]
            day = datetime.now(LOCAL).date() - timedelta(days=1)
            boundary = datetime.combine(day, time(), LOCAL)
            start, end = boundary - timedelta(minutes=2), boundary + timedelta(minutes=2)
            feed_url = os.getenv("TRACCAR_FEED_URL", "http://127.0.0.1:5055")
            with httpx.Client(timeout=15, trust_env=False) as feed:
                for index in range(5):
                    at = start + timedelta(minutes=index)
                    sent = feed.get(
                        feed_url,
                        params={
                            "id": unique,
                            "lat": 10.7769,
                            "lon": 106.7009,
                            "timestamp": at.isoformat(),
                            "speed": 0,
                            "bearing": 0,
                            "ignition": "true",
                            "odometer": 1000000,
                        },
                    )
                    assert sent.status_code == 200, sent.text
            adapter = Traccar(settings)
            deadline = monotonic() + 30
            while True:
                positions = adapter.get(
                    "positions",
                    {"deviceId": device["id"], "from": start.isoformat(), "to": end.isoformat()},
                )
                if len(positions) == 5:
                    break
                assert monotonic() < deadline, "Real Traccar did not persist all five observations"
                sleep(0.2)
            for beginning, ending, rate in ((start.date(), day, "1"), (day, None, "2")):
                result = client.post(
                    "/api/v1/fuel/profiles",
                    headers=header(tokens),
                    json={
                        "vehicle_id": vid,
                        "driving_l_per_100km": "8",
                        "idling_l_per_hour": rate,
                        "effective_from": beginning.isoformat(),
                        "effective_to": ending.isoformat() if ending else None,
                    },
                )
                assert result.status_code == 201, result.text
            created_entries = []
            for liters, cost, when in (("0.02", "100", start), ("0.03", "200", boundary)):
                result = client.post(
                    "/api/v1/fuel/entries",
                    headers=header(tokens, "DISPATCHER"),
                    json={
                        "vehicle_id": vid,
                        "liters": liters,
                        "client_action_id": str(uuid4()),
                        "amount": cost,
                        "filled_at": when.isoformat(),
                    },
                )
                assert result.status_code == 201, result.text
                created_entries.append(result.json())
            period = client.post(
                "/api/v1/fuel/reconciliations",
                headers=header(tokens, "DISPATCHER"),
                json={"vehicle_id": vid, "from_at": start.isoformat(), "to_at": end.isoformat()},
            )
            assert period.status_code == 201, period.text
            result = period.json()["versions"][0]["result_json"]
            assert result["data_status"] == "COMPLETE", result
            assert len(result["segments"]) == 2 and len(result["entries"]) == 2
            assert Decimal(result["actual_liters"]) == Decimal("0.05")
            assert Decimal(result["actual_cost"]) == 300
            assert abs(Decimal(result["expected_liters"]) - Decimal("0.1")) < Decimal("1e-20")
            assert abs(Decimal(result["variance_pct"]) - Decimal("-50")) < Decimal("1e-20")
            assert result["alert_flag"] is True
            assert sum(Decimal(s["idle_seconds"]) for s in result["segments"]) == 240
            original_version = period.json()["versions"][0]
            for actual, variance in (("0.085", 15), ("0.055", -15)):
                corrected = client.patch(
                    "/api/v1/fuel/entries/" + created_entries[0]["id"],
                    headers=header(tokens, "DISPATCHER"),
                    json={
                        "vehicle_id": vid,
                        "liters": actual,
                        "amount": "100",
                        "filled_at": start.isoformat(),
                        "reason": "Exact 15% regression",
                    },
                )
                assert corrected.status_code == 200, corrected.text
                recomputed = client.post(
                    "/api/v1/fuel/reconciliations/" + period.json()["id"] + "/recompute",
                    headers=header(tokens),
                    json={"reason": "Kiểm tra biên 15% với idle lặp"},
                )
                assert recomputed.status_code == 200, recomputed.text
                assert recomputed.json()["versions"][0] == original_version
                latest = recomputed.json()["versions"][-1]["result_json"]
                assert Decimal(latest["variance_pct"]) == variance
                assert latest["alert_flag"] is False
            # Also prove nonzero kilometre units from real Traccar odometer,
            # independently of the idle/profile-boundary case above.
            moving_start, moving_end = end + timedelta(minutes=10), end + timedelta(minutes=12)
            with httpx.Client(timeout=15, trust_env=False) as feed:
                for index in range(3):
                    sent = feed.get(
                        feed_url,
                        params={
                            "id": unique,
                            "lat": 10.7769 + index * 0.0009,
                            "lon": 106.7009,
                            "timestamp": (moving_start + timedelta(minutes=index)).isoformat(),
                            "speed": 3.24,
                            "bearing": 0,
                            "ignition": "true",
                            "odometer": 1000000 + index * 100,
                        },
                    )
                    assert sent.status_code == 200, sent.text
            added = client.post(
                "/api/v1/fuel/entries",
                headers=header(tokens, "DISPATCHER"),
                json={
                    "vehicle_id": vid,
                    "client_action_id": str(uuid4()),
                    "liters": "0.008",
                    "filled_at": moving_start.isoformat(),
                },
            )
            assert added.status_code == 201, added.text
            deadline = monotonic() + 30
            while (
                len(
                    adapter.get(
                        "positions",
                        {
                            "deviceId": device["id"],
                            "from": moving_start.isoformat(),
                            "to": moving_end.isoformat(),
                        },
                    )
                )
                < 3
            ):
                assert monotonic() < deadline, "Moving observations missing from real Traccar"
                sleep(0.2)
            moving = client.post(
                "/api/v1/fuel/reconciliations",
                headers=header(tokens),
                json={
                    "vehicle_id": vid,
                    "from_at": moving_start.isoformat(),
                    "to_at": moving_end.isoformat(),
                },
            )
            assert moving.status_code == 201, moving.text
            measured = moving.json()["versions"][0]["result_json"]
            assert measured["data_status"] == "COMPLETE", measured
            assert Decimal(measured["segments"][0]["distance_km"]) == Decimal("0.2")
            assert Decimal(measured["segments"][0]["idle_hours"]) == 0
            assert Decimal(measured["expected_liters"]) == Decimal("0.016")
            assert Decimal(measured["variance_pct"]) == -50 and measured["alert_flag"] is True
            print(
                "Real Traccar/PostGIS: profile boundary, observed idle once, two refills, "
                "signed variance PASS; simulated device only."
            )
        finally:
            # A timed-out POST can still commit. Lookup only this test's exact
            # uniqueId before cleanup, never touch canonical/other devices.
            candidates = (
                [device]
                if device
                else [
                    d
                    for d in traccar.get(base + "/api/devices").json()
                    if d.get("uniqueId") == unique
                ]
            )
            for candidate in candidates:
                removed = traccar.delete(base + f"/api/devices/{candidate['id']}")
                assert removed.status_code == 204, removed.text
