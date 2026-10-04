from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from fastapi import Request
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.engine import Connection, Engine

from app.config import get_settings


@lru_cache(maxsize=8)
def engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def database() -> Iterator[Connection]:
    engine = engine_for(get_settings().database_url.get_secret_value())
    with engine.begin() as connection:
        yield connection


@lru_cache(maxsize=64)
def table_for(name: str, engine: Engine) -> Table:
    return Table(name, MetaData(), autoload_with=engine)


def table(name: str, connection: Connection) -> Table:
    return table_for(name, connection.engine)


def audit(
    db: Connection,
    request: Request,
    actor: Any,
    action: str,
    resource: str,
    identifier: Any,
    before: Any = None,
    after: Any = None,
) -> None:
    # Callers pass only public DTOs: password/session/token material never enters audit.
    db.execute(
        table("audit_logs", db)
        .insert()
        .values(
            actor_user_id=actor,
            action=action,
            resource_type=resource,
            resource_id=str(identifier),
            before_json=before,
            after_json=after,
            request_id=request.state.request_id,
        )
    )
