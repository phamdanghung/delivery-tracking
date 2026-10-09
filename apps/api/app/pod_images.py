"""Validate bounded original image bytes without trusting filename or MIME claims."""

import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.config import Settings

FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


@dataclass(frozen=True)
class ImageInfo:
    sha256: str
    content_type: str
    size_bytes: int
    width: int
    height: int


def validate_image(data: bytes, content_type: str, settings: Settings) -> ImageInfo:
    if not data or len(data) > settings.pod_max_bytes:
        raise HTTPException(413, "Ảnh trống hoặc vượt giới hạn dung lượng POD")
    if content_type not in FORMATS.values():
        raise HTTPException(415, "POD chỉ nhận ảnh JPEG, PNG hoặc WebP")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=list(FORMATS)) as image:
                width, height = image.size
                if width * height > settings.pod_max_pixels:
                    raise HTTPException(413, "Ảnh vượt giới hạn số pixel POD")
                if FORMATS.get(image.format or "") != content_type:
                    raise HTTPException(415, "Định dạng ảnh không khớp MIME")
                if getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(415, "POD cần ảnh tĩnh")
                image.verify()
            with Image.open(BytesIO(data), formats=list(FORMATS)) as decoded:
                decoded.load()  # Reject truncated data; retain the original bytes unchanged.
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(422, "Nội dung ảnh POD không hợp lệ") from error
    return ImageInfo(hashlib.sha256(data).hexdigest(), content_type, len(data), width, height)
