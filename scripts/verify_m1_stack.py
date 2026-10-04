"""Verify real M1 services using scoped simulated GPS fixtures, never physical GPS."""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import Settings  # noqa: E402

settings = Settings(_env_file=root / ".env")
values = dict(
    line.split("=", 1)
    for line in (root / ".env").read_text(encoding="utf-8-sig").splitlines()
    if "=" in line and not line.startswith("#")
)
fixture = root / "artifacts/m1-ui-fixtures.json"
base, traccar_url = "http://127.0.0.1:8000/api/v1", settings.traccar_url.rstrip("/")
with httpx.Client(timeout=20, trust_env=False) as client:
    login = client.post(
        base + "/auth/login",
        json={
            "email": values["BOOTSTRAP_ADMIN_EMAIL"],
            "password": values["BOOTSTRAP_ADMIN_PASSWORD"],
        },
    )
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    auth = (settings.traccar_email, settings.traccar_password.get_secret_value())
    mode = sys.argv[1] if len(sys.argv) > 1 else "--prepare-ui"
    records = json.loads(fixture.read_text()) if fixture.exists() else []
    try:
        if mode == "--prepare-ui":
            assert not records, "Clean up the previous scoped UI fixtures first"
            for index, age in enumerate((0, 60, 180)):
                unique = "M1UI-" + uuid4().hex
                response = client.post(
                    traccar_url + "/api/devices",
                    auth=auth,
                    json={
                        "name": "M1 UI SIMULATED " + str(index),
                        "uniqueId": unique,
                    },
                )
                response.raise_for_status()
                record = {"device_id": response.json()["id"], "unique_id": unique, "age": age}
                records.append(record)
                fixture.write_text(json.dumps(records, indent=2))
                response = client.post(
                    base + "/vehicles",
                    headers=headers,
                    json={
                        "plate_no": "SIM-" + str(index + 1) + "-" + unique[-4:],
                        "name": "Dữ liệu mô phỏng M1 — " + ("NORMAL", "STALE", "LOST")[index],
                        "traccar_device_id": record["device_id"],
                    },
                )
                response.raise_for_status()
                record["vehicle_id"] = response.json()["id"]
                record["plate_no"] = response.json()["plate_no"]
                fixture.write_text(json.dumps(records, indent=2))
        if mode in ("--prepare-ui", "--feed-ui"):
            checks = []
            for index, record in enumerate(records):
                response = client.get(
                    "http://127.0.0.1:5055",
                    params={
                        "id": record["unique_id"],
                        "lat": 10.7769 + index * 0.005,
                        "lon": 106.7009 + index * 0.005,
                        "speed": 10 if index == 0 else 0,
                        "bearing": 90,
                        "ignition": "false" if index == 2 else "true",
                        "timestamp": (
                            datetime.now(UTC) - timedelta(seconds=record["age"])
                        ).isoformat(),
                    },
                )
                response.raise_for_status()
                expected = ("NORMAL", "STALE", "LOST")[index]
                for _ in range(20):
                    response = client.get(
                        base + f"/vehicles/{record['vehicle_id']}/live", headers=headers
                    )
                    response.raise_for_status()
                    if response.json()["position"] and response.json()["freshness"] == expected:
                        break
                    time.sleep(0.5)
                assert response.json()["freshness"] == expected, response.text
                assert (
                    response.json()["position"]["engine_state"]
                    == ("MOVING", "IDLING", "PARKED")[index]
                )
                checks.append(
                    {
                        "plate": record["plate_no"],
                        "freshness": response.json()["freshness"],
                        "engine": response.json()["position"]["engine_state"],
                    }
                )
            print(
                json.dumps(
                    {"source": "SIMULATED OsmAnd feed to REAL Docker Traccar", "checks": checks},
                    indent=2,
                )
            )
        elif mode == "--outage":
            assert records, "Prepare scoped fixtures before the outage verification"
            try:
                subprocess.run(
                    ["docker", "compose", "stop", "traccar"],
                    cwd=root,
                    check=True,
                    capture_output=True,
                )
                ready = client.get("http://127.0.0.1:8000/health/ready")
                live = client.get(
                    base + f"/vehicles/{records[0]['vehicle_id']}/live", headers=headers
                )
                assert ready.status_code == 503 and ready.json()["checks"]["traccar"] is False
                assert live.status_code == 503
                report = {
                    "real_traccar_stopped": True,
                    "readiness": ready.status_code,
                    "live_api": live.status_code,
                    "result": "PASS",
                }
                (root / "artifacts/m1-real-outage.json").write_text(json.dumps(report, indent=2))
                print(json.dumps(report))
            finally:
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "up",
                        "-d",
                        "--no-build",
                        "--wait",
                        "--wait-timeout",
                        "180",
                        "traccar",
                    ],
                    cwd=root,
                    check=True,
                    capture_output=True,
                )
        elif mode == "--cleanup-ui":
            for record in records:
                if record.get("vehicle_id"):
                    response = client.delete(
                        base + f"/vehicles/{record['vehicle_id']}", headers=headers
                    )
                    response.raise_for_status()
                response = client.delete(
                    traccar_url + f"/api/devices/{record['device_id']}", auth=auth
                )
                response.raise_for_status()
            fixture.unlink(missing_ok=True)
            print("Removed only the scoped M1 UI simulation fixtures; other data preserved.")
        else:
            raise RuntimeError("Unknown verification mode")
    finally:
        response = client.post(
            base + "/auth/logout",
            headers=headers,
            json={"refresh_token": login.json()["refresh_token"]},
        )
        response.raise_for_status()
