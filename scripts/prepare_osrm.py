"""Build a real self-hosted OSRM graph from a public OSM extract, never from customer data."""

import argparse
import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="https://download.bbbike.org/osm/bbbike/Saigon/Saigon.osm.pbf")
parser.add_argument("--directory", default="artifacts/osrm")
parser.add_argument("--image", default="ghcr.io/project-osrm/osrm-backend:v6.0.0")
parser.add_argument("--pbf", help="Use a versioned real OSM PBF instead of downloading")
parser.add_argument("--sha256", help="Required checksum when supplying --pbf")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
directory = (root / args.directory).resolve()
if not directory.is_relative_to(root):
    raise ValueError("OSRM build directory must remain in this workspace")
directory.mkdir(parents=True, exist_ok=True)
pbf = directory / "map.osm.pbf"
manifest = directory / "metadata.json"
previous = json.loads(manifest.read_text()) if manifest.exists() else None
if previous and previous["source_url"] != args.url:
    raise ValueError(
        "Different source URL: choose a separate --directory; existing graph preserved"
    )
if args.pbf:
    supplied = (root / args.pbf).resolve()
    if not supplied.is_relative_to(root) or not args.sha256:
        raise ValueError("Versioned PBF must be inside workspace with an explicit SHA256")
    supplied_digest = hashlib.sha256(supplied.read_bytes()).hexdigest()
    if supplied_digest != args.sha256:
        raise ValueError("Versioned OSM PBF checksum mismatch")
    if not pbf.exists() or hashlib.sha256(pbf.read_bytes()).hexdigest() != supplied_digest:
        temporary = directory / "download.part"
        shutil.copyfile(supplied, temporary)
        temporary.replace(pbf)
    print("Using checksum-verified real OSM PBF", supplied.name, flush=True)
if not pbf.exists():
    temporary = directory / "download.part"
    with urllib.request.urlopen(args.url, timeout=60) as source, temporary.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    temporary.replace(pbf)
    print("Downloaded public OSM road extract", pbf.stat().st_size, "bytes", flush=True)
digest = hashlib.sha256(pbf.read_bytes()).hexdigest()
if (
    previous
    and (directory / "map.osrm.partition").exists()
    and (directory / "map.osrm.mldgr").exists()
):
    if previous["sha256"] == digest and previous["image"] == args.image:
        print("Existing matching graph retained", digest, flush=True)
        raise SystemExit(0)
subprocess.run(["docker", "pull", args.image], check=True)
for executable, options in (
    ("osrm-extract", ["-p", "/opt/car.lua", "/data/map.osm.pbf", "--threads", "2"]),
    ("osrm-partition", ["/data/map.osrm", "--threads", "2"]),
    ("osrm-customize", ["/data/map.osrm", "--threads", "2"]),
):
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            str(directory) + ":/data",
            args.image,
            executable,
            *options,
        ],
        check=True,
    )
manifest.write_text(
    json.dumps(
        {
            "source_url": args.url,
            "sha256": digest,
            "image": args.image,
            "attribution": "Map data © OpenStreetMap contributors, ODbL 1.0; extract BBBike.org",
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("Real OSRM graph ready", digest, flush=True)
