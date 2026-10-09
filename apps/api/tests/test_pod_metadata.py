from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from pydantic import ValidationError

from app.pod_exif import strip_exif
from app.pod_metadata import PodMetadata


def metadata(**changes):
    now = datetime.now(UTC)
    return {
        "client_action_id": uuid4(),
        "trip_stop_id": uuid4(),
        "source": "CAMERA_CAPTURED",
        "captured_at": now,
        "sha256": "a" * 64,
        "location_status": "VERIFIED",
        "latitude": 10,
        "longitude": 106,
        "gps_fix_at": now,
        "gps_freshness": "NORMAL",
        **changes,
    }


@pytest.mark.parametrize("source", ["CAMERA_CAPTURED", "ALBUM_SELECTED"])
def test_valid_gps_and_source(source):
    result = PodMetadata.model_validate(metadata(source=source))
    assert result.source == source and result.latitude == 10


@pytest.mark.parametrize("freshness", ["STALE", "INVALID", "MISSING"])
def test_unverified_gps_allowed_with_explicit_reason(freshness):
    values = metadata(
        location_status="LOCATION_UNVERIFIED",
        gps_freshness=freshness,
        latitude=None,
        longitude=None,
        gps_fix_at=None,
        location_reason="Đã xác nhận không có GPS hợp lệ",
    )
    assert PodMetadata.model_validate(values).latitude is None
    with pytest.raises(ValidationError):
        PodMetadata.model_validate({**values, "location_reason": " "})
    with pytest.raises(ValidationError):
        PodMetadata.model_validate({**values, "latitude": 10, "longitude": 106})


@pytest.mark.parametrize("age", [-5, 31, 600])
def test_stale_or_future_fix_cannot_claim_verified(age):
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        PodMetadata.model_validate(
            metadata(captured_at=now, gps_fix_at=now - timedelta(seconds=age))
        )


@pytest.mark.parametrize(
    "format,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]
)
def test_false_exif_removed_without_changing_pixels_or_orientation(format, mime):
    exif = Image.Exif()
    exif[274] = 6
    exif[306] = "1900:01:01 00:00:00"
    exif[34853] = {1: "N", 2: (1, 2, 3), 3: "E", 4: (4, 5, 6)}
    original = BytesIO()
    Image.new("RGB", (9, 7), "red").save(original, format=format, exif=exif)
    cleaned = strip_exif(original.getvalue(), mime)
    with Image.open(BytesIO(original.getvalue())) as before, Image.open(BytesIO(cleaned)) as after:
        assert before.tobytes() == after.tobytes()
        assert after.getexif().get(274) == 6
        assert set(after.getexif()) == {274}
