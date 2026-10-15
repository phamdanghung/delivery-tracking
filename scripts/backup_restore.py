"""Consistent LOCAL backup and destructive-free restore drill into fresh owned volumes.

Never restore into canonical/legacy volumes. Production encryption, scheduling,
offsite storage, PITR and approved recovery objectives are separate deployment gates.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sql_inspect
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import Settings  # noqa: E402

LABEL = "fleet.restore-drill"
BACKUPS = root / "artifacts/backups"
ARCHIVES = {"minio": "/data", "traccar": "/opt/traccar/data"}


def docker(*args: str, data: bytes | None = None, env=None, output=None) -> bytes:
    try:
        result = subprocess.run(
            ["docker", *args],
            input=data,
            stdout=output or subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Docker operation timed out; details withheld") from None
    if result.returncode:
        # Docker/SQL stderr may contain environment/configuration secrets.
        raise RuntimeError("Docker operation failed; sensitive stderr withheld")
    return result.stdout or b""


def inspect(kind: str, name: str):
    return json.loads(docker(kind, "inspect", name))[0]


def private_directory(path: Path) -> None:
    path.mkdir(parents=True, mode=0o700, exist_ok=False)
    if os.name == "nt":
        identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
        sid = next(csv.reader(io.StringIO(identity)))[1]
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{sid}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
            ],
            check=True,
            capture_output=True,
        )
    else:
        path.chmod(0o700)


def bundle_path(value: Path) -> Path:
    value = value.resolve()
    if not value.is_relative_to(BACKUPS.resolve()) or value == BACKUPS.resolve():
        raise ValueError("Backup bundles must stay inside ignored artifacts/backups")
    return value


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def valid_source(project: str) -> bool:
    return (
        project == "fleet-delivery-dev"
        or re.fullmatch(r"fleet-delivery-backup-test-[0-9a-f]{16}", project) is not None
    )


def source_containers(project: str):
    if not valid_source(project):
        raise ValueError("Source must be canonical or a fresh isolated backup test project")
    result = {}
    for service in ("api", "postgres", "minio", "traccar"):
        ids = (
            docker(
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + project,
                "--filter",
                f"label=com.docker.compose.service={service}",
            )
            .decode()
            .splitlines()
        )
        if len(ids) != 1:
            raise RuntimeError("Expected exactly one canonical service: " + service)
        item = inspect("container", ids[0])
        if not item["State"]["Running"]:
            raise RuntimeError("Canonical service must be running before backup: " + service)
        result[service] = item
    return result


def backup(path: Path, database: str | None = None, project: str = "fleet-delivery-dev") -> dict:
    settings = Settings(_env_file=root / ".env")
    if settings.app_env != "local":
        raise ValueError("This backup adapter is approved for local development only")
    path = bundle_path(path)
    containers = source_containers(project)
    pg_env = dict(v.split("=", 1) for v in containers["postgres"]["Config"]["Env"] if "=" in v)
    dbname = database or pg_env["POSTGRES_DB"]
    if database and not re.fullmatch(r"fleet_delivery_m0_test_[0-9a-f]{12}", database):
        raise ValueError("Database override is limited to the existing isolated test harness")
    user = pg_env["POSTGRES_USER"]
    if not all(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", n) for n in (dbname, user)):
        raise ValueError("Unsupported database identifier")
    helper = inspect("image", "redis:7.4-alpine")["Id"]
    mounts = {}
    for service, destination in ARCHIVES.items():
        volume = next(m for m in containers[service]["Mounts"] if m["Destination"] == destination)
        if volume["Type"] != "volume" or not volume["Name"].startswith(project + "_"):
            raise ValueError("Source volume is outside canonical runtime")
        mounts[service] = volume["Name"]
    config = root / "infra/docker/traccar.xml"
    actual_config = next(
        m
        for m in containers["traccar"]["Mounts"]
        if m["Destination"] == "/opt/traccar/conf/traccar.xml"
    )
    if (
        Path(actual_config["Source"]).name != config.name
        or "jdbc:h2:./data/database" not in config.read_text()
    ):
        raise ValueError("Only the locked local H2 Traccar adapter is supported")
    private_directory(path)
    started = time.monotonic()
    stopped = []
    manifest = {
        "format": 1,
        "source_project": project,
        "database": dbname,
        "database_user": user,
        "created_at": datetime.now(UTC).isoformat(),
        "images": {k: v["Image"] for k, v in containers.items()},
        "helper_image": helper,
        "complete": False,
        "production_backup": False,
        "s3_bucket": settings.s3_bucket,
    }
    try:
        # API writes and Traccar/H2 ingestion stop before the object snapshot.
        # Stop cold object/H2 stores: copying a live volume is not a backup proof.
        for service in ("api", "traccar", "minio"):
            stopped.append(service)
            docker("stop", "--time", "60", containers[service]["Id"])
        url = make_url(settings.database_url.get_secret_value()).set(database=dbname)
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        try:
            with engine.connect() as db:
                db.execute(text("SET TIME ZONE 'UTC'"))
                tables = sql_inspect(db).get_table_names()
                fingerprints = {}
                for name in tables:
                    quoted = db.dialect.identifier_preparer.quote(name)
                    rows = db.execute(
                        text(f"SELECT to_jsonb(t)::text FROM {quoted} t ORDER BY 1")
                    ).scalars()
                    digest, count = hashlib.sha256(), 0
                    for row in rows:
                        digest.update(row.encode() + b"\n")
                        count += 1
                    fingerprints[name] = {"rows": count, "sha256": digest.hexdigest()}
                manifest["tables"] = fingerprints
                manifest["migration_head"] = db.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
        finally:
            engine.dispose()
        with (path / "database.dump").open("wb") as output:
            docker(
                "exec",
                containers["postgres"]["Id"],
                "pg_dump",
                "-U",
                user,
                "-d",
                dbname,
                "-Fc",
                "--no-owner",
                "--no-privileges",
                output=output,
            )
        for service, volume in mounts.items():
            docker(
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                "0",
                "--mount",
                f"type=volume,src={volume},dst=/source,readonly",
                "--mount",
                f"type=bind,src={path},dst=/backup",
                helper,
                "tar",
                "-czf",
                f"/backup/{service}.tar.gz",
                "-C",
                "/source",
                ".",
            )
        (path / "traccar.xml").write_bytes(config.read_bytes())
        manifest["files"] = {
            n: {"sha256": checksum(path / n), "size": (path / n).stat().st_size}
            for n in ("database.dump", "minio.tar.gz", "traccar.tar.gz", "traccar.xml")
        }
        manifest["complete"] = True
    finally:
        failures = []
        for service in reversed(stopped):
            try:
                docker("start", containers[service]["Id"])
            except RuntimeError:
                failures.append(service)
        manifest["restart_failures"] = failures
        manifest["backup_seconds"] = round(time.monotonic() - started, 3)
        (path / "manifest.json").write_text(json.dumps(manifest, indent=2))
        if failures:
            raise RuntimeError("Canonical restart requires attention: " + ",".join(failures))
    return {
        "bundle": str(path),
        "complete": manifest["complete"],
        "backup_seconds": manifest["backup_seconds"],
    }


def validate_bundle(path: Path) -> dict:
    path = bundle_path(path)
    data = json.loads((path / "manifest.json").read_text())
    expected = {"database.dump", "minio.tar.gz", "traccar.tar.gz", "traccar.xml"}
    if (
        data.get("format") != 1
        or not valid_source(data.get("source_project", ""))
        or data.get("complete") is not True
    ):
        raise ValueError("Not a complete local canonical backup")
    if set(data["files"]) != expected:
        raise ValueError("Unexpected bundle members")
    if set(data["images"]) != {"api", "postgres", "minio", "traccar"}:
        raise ValueError("Unexpected image set")
    if not all(
        re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", data[k]) for k in ("database", "database_user")
    ):
        raise ValueError("Unsupported database identifier")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", data["s3_bucket"]):
        raise ValueError("Unsupported storage bucket")
    for name in expected:
        item = path / name
        if (
            item.is_symlink()
            or item.stat().st_size != data["files"][name]["size"]
            or checksum(item) != data["files"][name]["sha256"]
        ):
            raise ValueError("Backup integrity check failed: " + name)
    for name in ("minio.tar.gz", "traccar.tar.gz"):
        with tarfile.open(path / name) as archive:
            for member in archive:
                parts = Path(member.name).parts
                if (
                    member.name.startswith(("/", "\\"))
                    or ".." in parts
                    or ":" in member.name
                    or "\\" in member.name
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("Unsafe archive member")
    for image in [data["helper_image"], *data["images"].values()]:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Image must be pinned by local image ID")
        inspect("image", image)
    return data


def owned(kind: str, name: str, identity: str) -> None:
    item = inspect(kind, name)
    labels = item.get("Labels") or item.get("Config", {}).get("Labels", {})
    if labels.get(LABEL) != identity or not name.startswith("fleet-delivery-restore-"):
        raise ValueError("Resource is not owned by this restore drill")


def restore_check(path: Path) -> dict:
    settings = Settings(_env_file=root / ".env")
    if settings.app_env != "local":
        raise ValueError("Restore drill supports local environment only")
    path, started = bundle_path(path), time.monotonic()
    data = validate_bundle(path)  # Validate everything BEFORE creating resources.
    identity = uuid4().hex
    prefix = "fleet-delivery-restore-" + identity[:16]
    network, containers, volumes = prefix + "-net", [], []
    environment = dict(
        os.environ,
        POSTGRES_USER=data["database_user"],
        POSTGRES_DB=data["database"],
        POSTGRES_PASSWORD=uuid4().hex + uuid4().hex,
        MINIO_ROOT_USER=settings.s3_access_key.get_secret_value(),
        MINIO_ROOT_PASSWORD=settings.s3_secret_key.get_secret_value(),
    )
    label = f"{LABEL}={identity}"
    report = {
        "target": prefix,
        "ownership_label": identity,
        "production_restore": False,
        "result": "FAIL",
        "owned_restore_resources_removed": False,
    }
    journal = path / (prefix + ".json")
    journal.write_text(json.dumps(report, indent=2))
    docker("network", "create", "--internal", "--label", label, network)
    try:
        for service in ("postgres", "minio", "traccar"):
            volume = prefix + "-" + service
            docker("volume", "create", "--label", label, volume)
            volumes.append(volume)
            if service != "postgres":
                docker(
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--user",
                    "0",
                    "--mount",
                    f"type=volume,src={volume},dst=/target",
                    "--mount",
                    f"type=bind,src={path},dst=/backup,readonly",
                    data["helper_image"],
                    "tar",
                    "-xzf",
                    f"/backup/{service}.tar.gz",
                    "-C",
                    "/target",
                )
            name = prefix + "-" + service
            args = ["create", "--name", name, "--label", label, "--network", network]
            destination = {"postgres": "/var/lib/postgresql/data", **ARCHIVES}[service]
            args += ["--mount", f"type=volume,src={volume},dst={destination}"]
            if service == "postgres":
                args += ["-e", "POSTGRES_USER", "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB"]
            elif service == "minio":
                args += ["-e", "MINIO_ROOT_USER", "-e", "MINIO_ROOT_PASSWORD"]
            else:
                logs = prefix + "-traccar-logs"
                docker("volume", "create", "--label", label, logs)
                volumes.append(logs)
                args += ["--mount", f"type=volume,src={logs},dst=/opt/traccar/logs"]
                args += [
                    "--mount",
                    f"type=bind,src={path / 'traccar.xml'},"
                    "dst=/opt/traccar/conf/traccar.xml,readonly",
                ]
            args += [data["images"][service]]
            if service == "minio":
                args += ["server", "/data"]
            docker(*args, env=environment)
            containers.append(name)
            docker("start", name)
        pg = prefix + "-postgres"
        deadline = time.monotonic() + 90
        while True:
            try:
                docker(
                    "exec",
                    pg,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    data["database_user"],
                    "-d",
                    data["database"],
                )
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        with (path / "database.dump").open("rb") as source:
            docker(
                "exec",
                "-i",
                pg,
                "pg_restore",
                "-U",
                data["database_user"],
                "-d",
                data["database"],
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                data=source.read(),
            )
        # Helper uses only this isolated network; no service ports are published.
        environment.update(
            RESTORE_PG=pg,
            RESTORE_MINIO=prefix + "-minio",
            RESTORE_TRACCAR=prefix + "-traccar",
            RESTORE_BUCKET=data["s3_bucket"],
            RESTORE_TRACCAR_EMAIL=settings.traccar_email,
            RESTORE_TRACCAR_PASSWORD=settings.traccar_password.get_secret_value(),
        )
        worker = root / "scripts/restore_probe.py"
        helper_name = prefix + "-probe"
        args = [
            "create",
            "--name",
            helper_name,
            "--label",
            label,
            "--network",
            network,
            "--entrypoint",
            "python",
        ]
        for key in (
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "MINIO_ROOT_USER",
            "MINIO_ROOT_PASSWORD",
            "RESTORE_PG",
            "RESTORE_MINIO",
            "RESTORE_TRACCAR",
            "RESTORE_BUCKET",
            "RESTORE_TRACCAR_EMAIL",
            "RESTORE_TRACCAR_PASSWORD",
        ):
            args += ["-e", key]
        args += [
            "--mount",
            f"type=bind,src={worker},dst=/restore_probe.py,readonly",
            "--mount",
            f"type=bind,src={path / 'manifest.json'},dst=/manifest.json,readonly",
            data["images"]["api"],
            "/restore_probe.py",
        ]
        docker(*args, env=environment)
        containers.append(helper_name)
        result = json.loads(docker("start", "-a", helper_name))
        report.update(result, result="PASS", restore_seconds=round(time.monotonic() - started, 3))
    finally:
        # Only UUID-named resources carrying THIS run's exact ownership label.
        for name in reversed(containers):
            owned("container", name, identity)
            docker("rm", "-f", name)
        for name in reversed(volumes):
            owned("volume", name, identity)
            docker("volume", "rm", name)
        owned("network", network, identity)
        docker("network", "rm", network)
        report["owned_restore_resources_removed"] = True
        journal.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "restore-check"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--database", help="Isolated test DB override; canonical DB is default")
    parser.add_argument("--project", default="fleet-delivery-dev")
    options = parser.parse_args()
    result = (
        backup(options.bundle, options.database, options.project)
        if options.action == "backup"
        else restore_check(options.bundle)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
