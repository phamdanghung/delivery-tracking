import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from scripts import backup_restore as recovery  # noqa: E402


@pytest.mark.parametrize(
    "source",
    [
        "fleet-delivery",
        "print-business-os",
        "fleet-delivery-dev-other",
        "fleet-delivery-restore-0123",
    ],
)
def test_backup_refuses_legacy_unrelated_and_restore_sources(source):
    with pytest.raises(ValueError):
        recovery.source_containers(source)


def test_restore_refuses_paths_outside_ignored_backup_directory(tmp_path):
    with pytest.raises(ValueError):
        recovery.bundle_path(tmp_path / "untrusted-backup")


def make_bundle(tmp_path, monkeypatch, member="./safe", *, symlink=False):
    monkeypatch.setattr(recovery, "BACKUPS", tmp_path)
    folder = tmp_path / "bundle"
    folder.mkdir()
    for name in ("minio.tar.gz", "traccar.tar.gz"):
        with tarfile.open(folder / name, "w:gz") as archive:
            info = tarfile.TarInfo(member)
            if symlink:
                info.type = tarfile.SYMTYPE
                info.linkname = "/private"
                archive.addfile(info)
            else:
                info.size = 3
                archive.addfile(info, io.BytesIO(b"abc"))
    (folder / "database.dump").write_bytes(b"fixture")
    (folder / "traccar.xml").write_bytes(b"fixture")
    data = {
        "format": 1,
        "source_project": "fleet-delivery-dev",
        "complete": True,
        "database": "fleet_delivery",
        "database_user": "fleet",
        "s3_bucket": "fleet-pod",
        "images": {k: "sha256:" + "1" * 64 for k in ("api", "postgres", "minio", "traccar")},
        "helper_image": "sha256:" + "1" * 64,
    }
    data["files"] = {
        p.name: {"size": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in folder.iterdir()
    }
    (folder / "manifest.json").write_text(json.dumps(data))
    return folder, data


@pytest.mark.parametrize(
    "member", ["../escape", "/absolute", "safe/../../escape", "C:/private", "safe\\..\\private"]
)
def test_untrusted_tar_paths_are_rejected_before_docker_is_called(tmp_path, monkeypatch, member):
    folder, _ = make_bundle(tmp_path, monkeypatch, member)
    monkeypatch.setattr(recovery, "inspect", lambda *a: pytest.fail("Must reject before Docker"))
    with pytest.raises(ValueError, match="Unsafe archive"):
        recovery.validate_bundle(folder)


def test_symlinks_and_corrupt_backup_are_rejected(tmp_path, monkeypatch):
    folder, _ = make_bundle(tmp_path, monkeypatch, symlink=True)
    with pytest.raises(ValueError, match="Unsafe archive"):
        recovery.validate_bundle(folder)
    (folder / "database.dump").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        recovery.validate_bundle(folder)


def test_incomplete_bundle_or_connection_string_in_database_name_is_rejected(tmp_path, monkeypatch):
    folder, data = make_bundle(tmp_path, monkeypatch)
    for field, value, match in (
        ("complete", False, "complete"),
        ("database", "host=production", "identifier"),
    ):
        changed = {**data, field: value}
        (folder / "manifest.json").write_text(json.dumps(changed))
        with pytest.raises(ValueError, match=match):
            recovery.validate_bundle(folder)
