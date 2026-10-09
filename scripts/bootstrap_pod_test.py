"""Initialize the explicitly configured isolated CI POD bucket, never business seed data."""

import os
import time

import boto3

bucket = os.environ["S3_BUCKET"]
assert os.environ["APP_ENV"] == "test" and bucket.startswith("fleet-pod-test-")
client = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT_URL"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
)
try:
    for attempt in range(30):
        try:
            client.list_buckets()
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
    client.create_bucket(Bucket=bucket)
    client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    assert client.get_bucket_versioning(Bucket=bucket)["Status"] == "Enabled"
    print("Isolated private CI POD bucket ready; versioning enabled.")
finally:
    client.close()
