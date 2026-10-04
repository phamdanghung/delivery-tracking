import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException
from websockets.asyncio.client import connect

from app.config import Settings, get_settings


class Traccar:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.settings.traccar_email or not self.settings.traccar_password.get_secret_value():
            raise HTTPException(503, "Traccar chưa được cấu hình xác thực")
        try:
            with httpx.Client(
                timeout=5,
                trust_env=False,
                auth=httpx.BasicAuth(
                    self.settings.traccar_email,
                    self.settings.traccar_password.get_secret_value(),
                ),
            ) as client:
                response = client.get(
                    self.settings.traccar_url.rstrip("/") + "/api/" + endpoint,
                    params=params,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                value = response.json()
                if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
                    raise ValueError("Invalid Traccar response")
                return value
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                503, "Không thể kết nối Traccar; dữ liệu cuối không phải vị trí trực tiếp"
            ) from exc

    def device_exists(self, device_id: int) -> bool:
        return any(item.get("id") == device_id for item in self.get("devices", {"id": device_id}))

    async def positions(self) -> AsyncIterator[dict[str, Any]]:
        base = self.settings.traccar_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.post(
                base + "/api/session",
                data={
                    "email": self.settings.traccar_email,
                    "password": self.settings.traccar_password.get_secret_value(),
                },
            )
            response.raise_for_status()
            cookie = "; ".join(f"{key}={value}" for key, value in client.cookies.items())
            socket = base.replace("http://", "ws://").replace("https://", "wss://") + "/api/socket"
            async with connect(
                socket,
                additional_headers={"Cookie": cookie},
                open_timeout=5,
                ping_interval=20,
                max_size=2**20,
            ) as websocket:
                async for message in websocket:
                    value = json.loads(message)
                    for position in value.get("positions", []):
                        if isinstance(position, dict):
                            yield position
