"""Verify the real dev migration and the full API suite in an isolated test database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import Settings  # noqa: E402 -- add the workspace API to the import path first

settings = Settings(_env_file=root / ".env")
dev_url = make_url(settings.database_url.get_secret_value())
test_name = "fleet_delivery_m0_test_" + uuid4().hex[:12]
admin = create_engine(
    dev_url.set(database="postgres"),
    isolation_level="AUTOCOMMIT",
    connect_args={"connect_timeout": 15},
)
test_created = False


def command(*args: str, url: str, test: bool = False) -> None:
    print("Running:", " ".join(args), flush=True)
    environment = dict(os.environ)
    environment.update(DATABASE_URL=url, APP_ENV="test" if test else "local")
    if test:
        environment["TEST_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", *args],
        cwd=root / "apps/api",
        env=environment,
        check=True,
        timeout=180,
    )


try:
    dev_connection = dev_url.render_as_string(hide_password=False)
    command("alembic", "upgrade", "head", url=dev_connection)
    engine = create_engine(dev_url, connect_args={"connect_timeout": 15})
    with engine.connect() as connection:
        print(
            "Dev migration:",
            connection.scalar(text("SELECT version_num FROM alembic_version")),
        )
        print("PostGIS:", connection.scalar(text("SELECT PostGIS_Version()")))
        print("Dev tables:", len(inspect(engine).get_table_names()))
    engine.dispose()
    with admin.connect() as connection:
        # Generated identifier contains only a fixed prefix and hexadecimal UUID characters.
        connection.exec_driver_sql(f'CREATE DATABASE "{test_name}"')
    test_created = True
    test_connection = dev_url.set(database=test_name).render_as_string(hide_password=False)
    command("alembic", "upgrade", "head", url=test_connection, test=True)
    command(
        "pytest",
        "-ra",
        "--junitxml=../../artifacts/m0-api-tests.xml",
        url=test_connection,
        test=True,
    )
    command("alembic", "downgrade", "base", url=test_connection, test=True)
    command("alembic", "upgrade", "head", url=test_connection, test=True)
    command("pytest", "-m", "integration", "-ra", url=test_connection, test=True)
    print("Real database verification PASS; upgrade/downgrade/upgrade PASS.")
finally:
    if test_created:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{test_name}"')
        print("Removed only the isolated database created by this verification run.")
    admin.dispose()
