import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import boto3
import httpx
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from botocore.config import Config
from redis import Redis
from sqlalchemy import create_engine, text

from app.config import Settings
from app.traccar import Traccar

logger = logging.getLogger("fleet")


def check_database(settings: Settings) -> None:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        connect_args={"connect_timeout": 3},
    )
    try:
        with engine.connect() as connection:
            configuration = AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            configuration.set_main_option(
                "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
            )
            if (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                != ScriptDirectory.from_config(configuration).get_current_head()
            ):
                raise RuntimeError("Database migration is not current")
            if not connection.scalar(text("SELECT PostGIS_Version()")):
                raise RuntimeError("PostGIS is not available")
    finally:
        engine.dispose()


def check_redis(settings: Settings) -> None:
    with Redis.from_url(
        settings.redis_url.get_secret_value(),
        socket_connect_timeout=3,
        socket_timeout=3,
    ) as client:
        if not client.ping():
            raise RuntimeError("Redis is not available")


def check_storage(settings: Settings) -> None:
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 0}),
    )
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    finally:
        client.close()


def check_traccar(settings: Settings) -> None:
    with httpx.Client(timeout=3) as client:
        client.get(f"{settings.traccar_url.rstrip('/')}/api/server").raise_for_status()
    if settings.traccar_email:
        Traccar(settings).get("devices")


async def probe(name: str, function: Callable[[Settings], Any], settings: Settings) -> bool:
    try:
        await asyncio.to_thread(function, settings)
        return True
    except Exception:
        # Never log exceptions containing connection URLs, credentials or tokens.
        logger.warning("dependency_unavailable", extra={"dependency": name})
        return False


async def readiness(settings: Settings) -> dict[str, bool]:
    checks = {
        "database": check_database,
        "redis": check_redis,
        "storage": check_storage,
        "traccar": check_traccar,
    }
    results = await asyncio.gather(*(probe(n, f, settings) for n, f in checks.items()))
    return dict(zip(checks, results, strict=True))
