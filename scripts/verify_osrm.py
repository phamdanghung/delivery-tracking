"""Infrastructure fixture only: real public roads in the downloaded Saigon extract."""

import json
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import Settings  # noqa: E402
from app.routing_provider import RoutingProvider, RoutingUnavailable  # noqa: E402

settings = Settings(_env_file=root / ".env")
provider = RoutingProvider(settings)
points = [(10.7769, 106.7009), (10.782, 106.693), (10.7769, 106.7009)]
for attempt in range(30):
    try:
        digest = provider.dataset()
        matrix = provider.matrix(points)
        route = provider.route(points)
        if matrix.distances_m[0][1] is None or len(route["geometry"]["coordinates"]) < 3:
            raise RoutingUnavailable("Road graph incomplete for infrastructure fixture")
        break
    except RoutingUnavailable:
        if attempt == 29:
            raise
        time.sleep(1)
report = {
    "provider": "self-hosted OSRM",
    "dataset_sha256": digest,
    "matrix": "PASS",
    "route_geometry": "PASS",
    "road_geometry_points": len(route["geometry"]["coordinates"]),
    "fixture": "public Saigon roads; not configured company coordinates",
}
(root / "artifacts").mkdir(exist_ok=True)
(root / "artifacts/m3-osrm-health.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
