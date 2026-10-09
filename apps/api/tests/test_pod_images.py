import hashlib
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.config import Settings
from app.pod_images import validate_image


def photo(format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 6), "white").save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize(
    "format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_original_image_bytes_and_hash_are_preserved(format: str, mime: str) -> None:
    original = photo(format)
    info = validate_image(original, mime, Settings())
    assert info.sha256 == hashlib.sha256(original).hexdigest()
    assert (info.width, info.height, info.size_bytes) == (8, 6, len(original))


@pytest.mark.parametrize(
    "data,mime,status",
    [
        (b"<svg></svg>", "image/png", 422),
        (photo(), "image/jpeg", 415),
        (photo()[:-20], "image/png", 422),
        (photo(), "image/svg+xml", 415),
        (b"", "image/png", 413),
    ],
)
def test_forged_corrupt_or_empty_upload_rejected(data: bytes, mime: str, status: int) -> None:
    with pytest.raises(HTTPException) as error:
        validate_image(data, mime, Settings())
    assert error.value.status_code == status


def test_pixel_and_byte_limits_checked_before_decode() -> None:
    for data, settings in [
        (photo(), Settings(pod_max_pixels=40)),
        (b"x" * 1025, Settings(pod_max_bytes=1024)),
    ]:
        with pytest.raises(HTTPException) as error:
            validate_image(data, "image/png", settings)
        assert error.value.status_code == 413
