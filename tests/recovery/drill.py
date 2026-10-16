"""Explicit recovery scenario; invoked by verify_recovery.py locally AND in CI."""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from scripts.backup_restore import backup, restore_check
from test_m1_api import context as context
from test_m1_api import header
from test_m3_api import approve, optimize, route_trip
from test_m5_api import delivering, payload, photo, upload

from app.config import get_settings

pytestmark = pytest.mark.integration


def test_private_photo_database_audit_and_traccar_survive_actual_restore(context, monkeypatch):
    client, _, _, tokens = context
    trip, departure = route_trip(context)
    plan = optimize(context, trip, departure)
    assert plan.status_code == 200, plan.text
    assert approve(context, trip, plan.json()).status_code == 200
    response = client.post(f"/api/v1/trips/{trip['id']}/start", headers=header(tokens, "DRIVER"))
    assert response.status_code == 200
    stop = trip["stops"][0]
    delivering(context, stop)
    image = photo()
    uploaded = upload(context, stop, image, payload(stop, image))
    assert uploaded.status_code == 201
    settings = get_settings()
    unique = "M8RESTORE-" + uuid4().hex
    directory = Path(os.environ["M8_RECOVERY_DIRECTORY"])
    project = os.environ["M8_RECOVERY_PROJECT"]
    assert project.startswith("fleet-delivery-backup-test-")
    bundle = Path(__file__).resolve().parents[2] / "artifacts/backups" / ("drill-" + uuid4().hex)
    with httpx.Client(
        base_url=settings.traccar_url,
        timeout=30,
        trust_env=False,
        auth=(settings.traccar_email, settings.traccar_password.get_secret_value()),
    ) as traccar:
        device = traccar.post(
            "/api/devices", json={"name": "M8 ISOLATED GPS restore canary", "uniqueId": unique}
        )
        assert device.status_code == 200
        device_id = device.json()["id"]
        with httpx.Client(timeout=20, trust_env=False) as feed:
            sent = feed.get(
                os.environ["TRACCAR_FEED_URL"],
                params={
                    "id": unique,
                    "lat": 10.7769,
                    "lon": 106.7009,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "speed": 0,
                    "bearing": 0,
                    "ignition": "false",
                },
            )
            assert sent.status_code == 200
        devices = traccar.get("/api/devices").json()
        deadline = time.monotonic() + 30
        while True:
            positions = traccar.get("/api/positions").json()
            if any(p["deviceId"] == device_id for p in positions):
                break
            assert time.monotonic() < deadline, "Real GPS observation was not persisted"
            time.sleep(0.2)
        identities = sorted((d["id"], d["uniqueId"]) for d in devices)
        position_ids = sorted(p["id"] for p in positions)
        # Only this isolated project is quiesced. Canonical/legacy are untouched.
        with monkeypatch.context() as local:
            local.setenv("APP_ENV", "local")
            saved = backup(bundle, project=project)
            assert saved["complete"] is True
            result = restore_check(bundle)
        assert result["result"] == "PASS"
        manifest = json.loads((bundle / "manifest.json").read_text())
        assert result["table_fingerprints_verified"] == len(manifest["tables"])
        assert manifest["tables"]["pod_photos"]["rows"] == 1
        assert manifest["tables"]["audit_logs"]["rows"] > 0
        assert result["private_versioned_assets_verified"] == 1
        assert result["original_object_version_ids_preserved"] is True
        assert result["anonymous_storage_read"] == 403
        assert (
            result["traccar_device_identities_sha256"]
            == hashlib.sha256(json.dumps(identities).encode()).hexdigest()
        )
        assert (
            result["traccar_latest_position_ids_sha256"]
            == hashlib.sha256(json.dumps(position_ids).encode()).hexdigest()
        )
        assert result["owned_restore_resources_removed"] is True
        (directory / "scenario.json").write_text(
            json.dumps({"backup": saved, "restore": result}, indent=2)
        )
