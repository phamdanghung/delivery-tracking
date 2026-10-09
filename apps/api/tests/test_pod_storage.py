import hashlib
from io import BytesIO

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from fastapi import HTTPException

from app import pod_storage
from app.config import Settings
from app.pod_images import ImageInfo


@pytest.mark.parametrize(
    "scenario", ["created", "retry", "different", "unversioned", "unavailable"]
)
def test_conditional_upload_and_failure_recovery(monkeypatch, scenario: str) -> None:
    data = b"verified-original-image"
    info = ImageInfo(hashlib.sha256(data).hexdigest(), "image/png", len(data), 8, 6)
    settings = Settings()
    client = boto3.client("s3", aws_access_key_id="test", aws_secret_access_key="test")
    monkeypatch.setattr(pod_storage, "storage_client", lambda _: client)
    params = {
        "Bucket": settings.s3_bucket,
        "Key": "pod/test",
        "Body": data,
        "ContentType": "image/png",
        "IfNoneMatch": "*",
        "Metadata": {"sha256": info.sha256},
    }
    with Stubber(client) as stub:
        if scenario in {"retry", "different"}:
            stub.add_client_error(
                "put_object", "PreconditionFailed", http_status_code=412, expected_params=params
            )
            existing = data if scenario == "retry" else b"different-image"
            stub.add_response(
                "get_object",
                {
                    "Body": StreamingBody(BytesIO(existing), len(existing)),
                    "ContentType": "image/png",
                    "VersionId": "original-version",
                },
                {"Bucket": settings.s3_bucket, "Key": "pod/test"},
            )
        elif scenario == "unavailable":
            stub.add_client_error(
                "put_object", "ServiceUnavailable", http_status_code=503, expected_params=params
            )
        else:
            stub.add_response(
                "put_object",
                {"VersionId": "original-version"} if scenario == "created" else {},
                params,
            )

        if scenario in {"created", "retry"}:
            assert (
                pod_storage.store_original(settings, "pod/test", data, info) == "original-version"
            )
        else:
            with pytest.raises(HTTPException) as error:
                pod_storage.store_original(settings, "pod/test", data, info)
            assert error.value.status_code == (409 if scenario == "different" else 503)
        stub.assert_no_pending_responses()
