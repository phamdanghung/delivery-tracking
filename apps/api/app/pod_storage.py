"""Private immutable POD objects: retrying a PUT must not create another version."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from app.config import Settings
from app.pod_images import ImageInfo

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client


def storage_client(settings: Settings, *, public: bool = False) -> S3Client:
    return boto3.client(
        "s3",
        endpoint_url=(settings.s3_public_endpoint_url or settings.s3_endpoint_url)
        if public
        else settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        config=Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 1}),
    )


def store_original(settings: Settings, key: str, data: bytes, info: ImageInfo) -> str:
    client = storage_client(settings)
    try:
        try:
            result = client.put_object(
                Bucket=settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=info.content_type,
                IfNoneMatch="*",
                Metadata={"sha256": info.sha256},
            )
            version = result.get("VersionId")
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 412:
                raise
            existing = client.get_object(Bucket=settings.s3_bucket, Key=key)
            stream = existing["Body"]
            try:
                content = stream.read(settings.pod_max_bytes + 1)
            finally:
                stream.close()
            if (
                len(content) != info.size_bytes
                or hashlib.sha256(content).hexdigest() != info.sha256
                or existing.get("ContentType") != info.content_type
            ):
                raise HTTPException(409, "Object POD đã tồn tại với nội dung khác") from error
            version = existing.get("VersionId")
        if not version or version == "null":
            raise HTTPException(503, "Storage POD cần bật versioning")
        return version
    except (ClientError, BotoCoreError) as error:
        raise HTTPException(503, "Storage POD chưa sẵn sàng; giữ ảnh để thử lại") from error
    finally:
        client.close()
