"""Run a real POD/GPS backup/restore drill in a fresh scoped source and target.

Neither canonical nor legacy is stopped or modified by this verification.
"""

import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import boto3
from backup_restore import docker, inspect, private_directory
from sqlalchemy import create_engine, text

root = Path(__file__).resolve().parents[1]


def run_drill() -> None:
    sys.path.insert(0, str(root / "apps/api"))
    from app.config import Settings

    # This drill exercises an approved route/POD through the real locked solver.
    # OSRM is read-only; reuse the configured canonical/CI routing service.
    routing_url = Settings(_env_file=root / ".env").osrm_url
    if not routing_url:
        raise RuntimeError("Configure a real self-hosted OSRM_URL before the recovery drill")
    identity = uuid4().hex[:16]
    project = "fleet-delivery-backup-test-" + identity
    directory = root / "artifacts/recovery" / identity
    private_directory(directory)
    environment = dict(
        os.environ,
        RECOVERY_ID=identity,
        RECOVERY_PASSWORD=secrets.token_urlsafe(32),
        RECOVERY_JWT_SECRET=secrets.token_urlsafe(48),
        RECOVERY_DATABASE="fleet_delivery_m0_test_" + uuid4().hex[:12],
    )
    compose = ["docker", "compose", "-p", project, "-f", str(root / "infra/recovery.compose.yaml")]
    for resource in ("container", "volume", "network"):
        values = docker(
            resource,
            "ls",
            "-aq" if resource == "container" else "-q",
            "--filter",
            "label=com.docker.compose.project=" + project,
        )
        if values.strip():
            raise RuntimeError("Test project namespace is not empty")
    report = {"source_project": project, "canonical_touched": False, "result": "FAIL"}
    log = directory / "verification.log"

    def command(args, *, cwd=root, timeout=600):
        with log.open("ab") as output:
            result = subprocess.run(
                args,
                cwd=cwd,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        if result.returncode:
            # CI must expose a useful failure without publishing the private
            # bundle, request logs or randomly generated credentials.
            secrets_to_redact = [
                value
                for key, value in environment.items()
                if any(part in key for part in ("PASSWORD", "SECRET", "ACCESS_KEY", "DATABASE_URL"))
                and len(value) >= 4
            ]
            for line in log.read_text(errors="replace").splitlines():
                location = re.search(
                    r"(?:backup_restore|restore_probe|drill)\.py:\d+: in \w+", line
                )
                if location:
                    print(location.group(0), flush=True)
                if line.startswith(("E ", "FAILED ")):
                    for value in secrets_to_redact:
                        line = line.replace(value, "[REDACTED]")
                    print(line[:1000], flush=True)
            raise RuntimeError("Recovery verification failed; private diagnostic log: " + str(log))

    def endpoint(service: str, port: int) -> str:
        ids = subprocess.check_output(
            [*compose, "ps", "-q", service], env=environment, text=True
        ).splitlines()
        if len(ids) != 1:
            raise RuntimeError("Missing isolated service")
        item = inspect("container", ids[0])
        assert item["Config"]["Labels"]["fleet.recovery-source"] == identity
        bindings = item["NetworkSettings"]["Ports"][f"{port}/tcp"]
        assert len(bindings) == 1 and bindings[0]["HostIp"] == "127.0.0.1"
        return "127.0.0.1:" + bindings[0]["HostPort"]

    try:
        print("Building isolated recovery images", flush=True)
        command([*compose, "build", "api", "minio"])
        command(
            [
                *compose,
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "postgres",
                "minio",
                "traccar",
            ]
        )
        pg, storage, traccar, feed = (
            endpoint("postgres", 5432),
            endpoint("minio", 9000),
            endpoint("traccar", 8082),
            endpoint("traccar", 5055),
        )
        environment.update(
            APP_ENV="local",
            DATABASE_URL=f"postgresql+psycopg://fleet_recovery:{environment['RECOVERY_PASSWORD']}@{pg}/{environment['RECOVERY_DATABASE']}",
            S3_ENDPOINT_URL="http://" + storage,
            S3_PUBLIC_ENDPOINT_URL="http://" + storage,
            S3_ACCESS_KEY="fleet_recovery",
            S3_SECRET_KEY=environment["RECOVERY_PASSWORD"],
            S3_BUCKET="recovery-pod",
            TRACCAR_URL="http://" + traccar,
            TRACCAR_FEED_URL="http://" + feed,
            TRACCAR_EMAIL="restore-drill@fleet.local",
            TRACCAR_PASSWORD=secrets.token_urlsafe(32),
            JWT_SECRET=environment["RECOVERY_JWT_SECRET"],
            M8_RECOVERY_PROJECT=project,
            M8_RECOVERY_DIRECTORY=str(directory),
            OSRM_URL=routing_url,
            PYTHONPATH=os.pathsep.join(
                (str(root), str(root / "apps/api"), str(root / "apps/api/tests"))
            ),
        )
        environment["TEST_DATABASE_URL"] = environment["DATABASE_URL"]
        # Check the actual host-facing SQL connection too: a local socket
        # pg_isready can succeed against the temporary bootstrap server.
        engine = create_engine(environment["DATABASE_URL"], connect_args={"connect_timeout": 3})
        deadline = time.monotonic() + 60
        try:
            while True:
                try:
                    with engine.connect() as connection:
                        assert connection.scalar(text("SELECT 1")) == 1
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Isolated host-facing PostgreSQL did not become ready"
                        ) from None
                    time.sleep(1)
        finally:
            engine.dispose()
        client = boto3.client(
            "s3",
            endpoint_url=environment["S3_ENDPOINT_URL"],
            aws_access_key_id=environment["S3_ACCESS_KEY"],
            aws_secret_access_key=environment["S3_SECRET_KEY"],
        )
        try:
            client.create_bucket(Bucket="recovery-pod")
            client.put_bucket_versioning(
                Bucket="recovery-pod", VersioningConfiguration={"Status": "Enabled"}
            )
        finally:
            client.close()
        command([sys.executable, str(root / "scripts/bootstrap_traccar_test.py")])
        command([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root / "apps/api")
        command([*compose, "up", "-d", "--no-deps", "--wait", "--wait-timeout", "180", "api"])
        print("Running actual private POD/Traccar restore scenario", flush=True)
        command(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                str(root / "apps/api/pyproject.toml"),
                str(root / "tests/recovery/drill.py"),
                "-q",
                "--tb=short",
                "-s",
            ]
        )
        report.update(json.loads((directory / "scenario.json").read_text()), result="PASS")
    except Exception:
        with log.open("ab") as output:
            subprocess.run(
                [*compose, "logs", "--no-color", "--tail", "60", "postgres"],
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
        raise
    finally:
        # Validate scope/ownership before Compose removes only this test project's resources.
        for kind in ("container", "volume", "network"):
            for name in (
                docker(
                    kind,
                    "ls",
                    "-aq" if kind == "container" else "-q",
                    "--filter",
                    "label=com.docker.compose.project=" + project,
                )
                .decode()
                .splitlines()
            ):
                item = inspect(kind, name)
                labels = item.get("Labels") or item.get("Config", {}).get("Labels", {})
                if labels.get("fleet.recovery-source") != identity:
                    raise RuntimeError("Refusing cleanup: test resource ownership differs")
        command([*compose, "down", "--volumes"])
        report["isolated_source_removed"] = True
        (directory / "result.json").write_text(json.dumps(report, indent=2))
        (root / "artifacts/m8-recovery-result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_drill()
