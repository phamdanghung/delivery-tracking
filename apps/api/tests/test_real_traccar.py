import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from test_m1_api import context as context
from test_m1_api import header

from app.config import get_settings
from app.traccar import Traccar


@pytest.mark.integration
def test_real_traccar_rest_socket_feed_and_three_vehicle_mapping(context):
    client, _, _, tokens = context
    settings = get_settings()
    assert settings.traccar_email and settings.traccar_password.get_secret_value(), (
        "Real Traccar credentials are mandatory"
    )
    adapter = Traccar(settings)
    base = settings.traccar_url.rstrip("/")
    devices, vehicles = [], []
    with httpx.Client(
        timeout=15,
        trust_env=False,
        auth=(settings.traccar_email, settings.traccar_password.get_secret_value()),
    ) as traccar:
        try:
            for index in range(3):
                unique = "M1SIM-" + uuid4().hex
                response = traccar.post(
                    base + "/api/devices",
                    json={"name": "M1 SIMULATED " + str(index), "uniqueId": unique},
                )
                assert response.status_code == 200, "Real Traccar device creation failed"
                device = response.json()
                devices.append(device)
                response = client.post(
                    "/api/v1/vehicles",
                    headers=header(tokens),
                    json={
                        "plate_no": "SIM-" + unique[-8:],
                        "name": "Dữ liệu mô phỏng M1",
                        "traccar_device_id": device["id"],
                    },
                )
                assert response.status_code == 201, response.text
                vehicles.append(response.json())
            target = devices[0]
            feed_url = os.getenv("TRACCAR_FEED_URL", "http://127.0.0.1:5055")

            async def verify_socket():
                async def observe():
                    async for position in adapter.positions():
                        if position.get("deviceId") == target["id"]:
                            return position
                    raise AssertionError("Socket ended before simulated position")

                receiver = asyncio.create_task(observe())
                try:
                    await asyncio.sleep(1)
                    async with httpx.AsyncClient(timeout=15, trust_env=False) as feed:
                        response = await feed.get(
                            feed_url,
                            params={
                                "id": target["uniqueId"],
                                "lat": 10.7769,
                                "lon": 106.7009,
                                "timestamp": datetime.now(UTC).isoformat(),
                                "speed": 10,
                                "bearing": 90,
                                "ignition": "true",
                            },
                        )
                        response.raise_for_status()
                    return await asyncio.wait_for(receiver, timeout=20)
                finally:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)

            socket_position = asyncio.run(verify_socket())
            assert socket_position["deviceId"] == target["id"]
            response = client.get(
                f"/api/v1/vehicles/{vehicles[0]['id']}/live", headers=header(tokens)
            )
            assert response.status_code == 200, response.text
            live = response.json()
            assert live["position"]["latitude"] == 10.7769
            assert live["position"]["speed_kmh"] == 18.52
            assert live["position"]["engine_state"] == "MOVING"
            assert live["freshness"] == "NORMAL"
            start, end = (
                datetime.now(UTC) - timedelta(minutes=5),
                datetime.now(UTC) + timedelta(seconds=1),
            )
            parameters = {"from": start.isoformat(), "to": end.isoformat()}
            response = client.get(
                f"/api/v1/vehicles/{vehicles[0]['id']}/history",
                headers=header(tokens),
                params=parameters,
            )
            assert response.status_code == 200
            assert response.json()["points"]
            response = client.get(
                f"/api/v1/vehicles/{vehicles[0]['id']}/odometer",
                headers=header(tokens),
                params=parameters,
            )
            assert response.status_code == 200, response.text
            assert response.json()["distance_km"] >= 0
            print(
                "REAL TRACCAR: REST + WebSocket + OsmAnd SIMULATED feed + 3 mappings PASS; "
                "no physical GPS acceptance."
            )
        finally:
            for vehicle in vehicles:
                response = client.delete(
                    f"/api/v1/vehicles/{vehicle['id']}", headers=header(tokens)
                )
                assert response.status_code == 204
            for device in devices:
                response = traccar.delete(base + f"/api/devices/{device['id']}")
                assert response.status_code == 204
