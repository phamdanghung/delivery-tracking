"""Self-hosted OSRM adapter. Coordinates only; no geocoding or fallback."""

import json
import math
import socket
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import Settings
from app.route_optimizer import TravelMatrix


class RoutingUnavailable(ValueError):
    pass


class RoutingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        parsed = urlsplit(settings.osrm_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            raise RoutingUnavailable("Thiếu/sai cấu hình OSRM self-host")
        self.url = settings.osrm_url.rstrip("/")

    def dataset(self) -> str:
        try:
            path = Path(self.settings.osrm_metadata_path)
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[3] / path
            metadata = json.loads(path.read_text())
            digest = metadata["sha256"]
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("Invalid dataset digest")
            return digest
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RoutingUnavailable("Thiếu metadata/hash dữ liệu đường OSRM") from exc

    def request(self, service: str, points: list[tuple[float, float]], **params: str) -> Any:
        coordinates = ";".join(f"{lon},{lat}" for lat, lon in points)
        try:
            host = urlsplit(self.url).hostname
            addresses = socket.getaddrinfo(str(host), None)
            if not addresses or any(
                not (ip_address(item[4][0]).is_private or ip_address(item[4][0]).is_loopback)
                for item in addresses
            ):
                raise ValueError("OSRM must resolve to a self-hosted local/private address")
            with httpx.Client(
                timeout=self.settings.osrm_timeout_seconds, follow_redirects=False, trust_env=False
            ) as client:
                response = client.get(
                    f"{self.url}/{service}/v1/driving/{coordinates}", params=params
                )
                response.raise_for_status()
                data = response.json()
            if data.get("code") != "Ok":
                raise ValueError("OSRM could not route all points")
            return data
        except (httpx.HTTPError, OSError, ValueError, AttributeError) as exc:
            raise RoutingUnavailable(
                "OSRM unavailable hoặc không có đường đi cho các điểm; không fallback"
            ) from exc

    def matrix(self, points: list[tuple[float, float]]) -> TravelMatrix:
        data = self.request("table", points, annotations="distance,duration")
        try:

            def units(name: str) -> tuple[tuple[int | None, ...], ...]:
                result = []
                for row in data[name]:
                    values: list[int | None] = []
                    for value in row:
                        if value is None:
                            values.append(None)
                        elif type(value) in {int, float} and math.isfinite(value) and value >= 0:
                            values.append(math.ceil(value))
                        else:
                            raise ValueError("Invalid matrix unit")
                    result.append(tuple(values))
                return tuple(result)

            matrix = TravelMatrix(units("distances"), units("durations"))
            matrix.validate(len(points))
            return matrix
        except (KeyError, TypeError, ValueError) as exc:
            raise RoutingUnavailable("OSRM trả matrix không hợp lệ") from exc

    def route(self, points: list[tuple[float, float]]) -> dict[str, Any]:
        data = self.request(
            "route",
            points,
            overview="full",
            geometries="geojson",
            steps="false",
            continue_straight="false",
        )
        try:
            route = data["routes"][0]
            geometry = route["geometry"]
            if geometry["type"] != "LineString" or len(route["legs"]) != len(points) - 1:
                raise ValueError("Invalid route detail")
            if len(geometry["coordinates"]) < 2:
                raise ValueError("Missing road geometry")
            for lon, lat in geometry["coordinates"]:
                if (
                    not math.isfinite(lon)
                    or not math.isfinite(lat)
                    or not -180 <= lon <= 180
                    or not -90 <= lat <= 90
                ):
                    raise ValueError("Invalid geometry coordinate")
            return dict(route)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RoutingUnavailable("OSRM trả route geometry/detail không hợp lệ") from exc
