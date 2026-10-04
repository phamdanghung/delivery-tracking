"""Initialize only new local credentials/accounts; never reset an existing account."""

import secrets
import sys
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.auth import hasher  # noqa: E402
from app.config import Settings  # noqa: E402
from app.database import table  # noqa: E402

env_file = root / ".env"
if not env_file.exists():
    raise RuntimeError("Run scripts/dev.ps1 -ConfigureOnly first")
contents = env_file.read_text(encoding="utf-8-sig")
defaults = {
    "JWT_SECRET": secrets.token_urlsafe(48),
    "TRACCAR_EMAIL": "adapter@fleet.local",
    "TRACCAR_PASSWORD": secrets.token_urlsafe(32),
    "BOOTSTRAP_ADMIN_EMAIL": "admin@fleet.local",
    "BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(24),
}
for key, value in defaults.items():
    lines = contents.splitlines()
    existing = next((line for line in lines if line.startswith(key + "=")), None)
    if existing is None:
        contents += f"\n{key}={value}\n"
    elif not existing.split("=", 1)[1].strip():
        contents = contents.replace(existing, f"{key}={value}")
env_file.write_text(contents, encoding="utf-8")
if "--configure-only" in sys.argv:
    print("M1 local credentials configured in ignored .env; existing values preserved.")
    raise SystemExit(0)
values = dict(
    line.split("=", 1) for line in contents.splitlines() if "=" in line and not line.startswith("#")
)
settings = Settings(_env_file=env_file)
with httpx.Client(timeout=15, trust_env=False) as client:
    server = client.get(settings.traccar_url.rstrip("/") + "/api/server")
    server.raise_for_status()
    if server.json().get("newServer") is True:
        response = client.post(
            settings.traccar_url.rstrip("/") + "/api/users",
            json={
                "name": "M1 local adapter",
                "email": settings.traccar_email,
                "password": settings.traccar_password.get_secret_value(),
            },
        )
        response.raise_for_status()
        print(
            "Created first account on new local Traccar server; credentials remain in ignored .env."
        )
    # Verify configured credentials; do not overwrite/reset existing users.
    response = client.get(
        settings.traccar_url.rstrip("/") + "/api/devices",
        auth=(settings.traccar_email, settings.traccar_password.get_secret_value()),
    )
    response.raise_for_status()
engine = create_engine(settings.database_url.get_secret_value())
with engine.begin() as db:
    users = table("users", db)
    if db.execute(select(users.c.id).limit(1)).first() is None:
        db.execute(
            users.insert().values(
                full_name="Quản trị local",
                email=values["BOOTSTRAP_ADMIN_EMAIL"],
                password_hash=hasher.hash(values["BOOTSTRAP_ADMIN_PASSWORD"]),
                role="ADMIN",
            )
        )
        print("Created first local application ADMIN; credentials remain in ignored .env.")
engine.dispose()
print("M1 bootstrap verified; no secrets printed, existing accounts preserved.")
