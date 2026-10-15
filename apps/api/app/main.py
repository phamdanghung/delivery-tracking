import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import (
    auth,
    deliveries,
    driver,
    expense_receipts,
    expenses,
    fleet,
    fuel,
    geofence,
    gps,
    maintenance,
    pod,
    routes,
    safety,
    tracking,
    vehicle_receipts,
)
from app.config import get_settings
from app.deployment_policy import enforce_production_config
from app.health import readiness


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {"level": record.levelname, "message": record.getMessage()}
        for key in (
            "request_id",
            "method",
            "status_code",
            "duration_ms",
            "dependency",
            "route_template",
        ):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields)


logger = logging.getLogger("fleet")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
                if scope["path"].startswith("/api/v1/"):
                    message["headers"].extend(
                        [
                            (b"cache-control", b"no-store"),
                            (b"referrer-policy", b"no-referrer"),
                            (b"x-robots-tag", b"noindex, nofollow"),
                            (b"x-content-type-options", b"nosniff"),
                            (b"x-frame-options", b"DENY"),
                        ]
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "route_template": getattr(scope.get("route"), "path", "UNMATCHED"),
                },
            )


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    enforce_production_config(settings)
    tasks = []
    if settings.app_env != "test" and settings.traccar_email:
        tasks = [asyncio.create_task(gps.poll_worker()), asyncio.create_task(gps.socket_worker())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


settings = get_settings()
app = FastAPI(title="Fleet Delivery API — M7", version="1.7.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(fleet.router)
app.include_router(gps.router)
app.include_router(deliveries.router)
app.include_router(routes.router)
app.include_router(driver.router)
app.include_router(geofence.router)
app.include_router(pod.router)
app.include_router(tracking.router)
app.include_router(fuel.router)
app.include_router(maintenance.router)
app.include_router(safety.router)
app.include_router(expenses.router)
app.include_router(expense_receipts.router)
app.include_router(vehicle_receipts.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-POD-Metadata", "X-Receipt-Metadata"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.get("/health/live", tags=["operations"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["operations"])
async def ready() -> Response:
    checks = await readiness(settings)
    healthy = all(checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
    )
