"""Read-only configuration/database/log review.

Exit 0 means review written, NOT production-ready.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import Settings  # noqa: E402
from app.deployment_policy import production_config_issues  # noqa: E402
from app.gps import freshness  # noqa: E402
from app.operational_metrics import p95, summarize_logs  # noqa: E402


def review(log: Path | None = None) -> dict:
    settings = Settings(_env_file=root / ".env")
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "environment": settings.app_env,
        "production_ready": False,
        "production_environment_configured": settings.app_env == "production",
        "production_config_issues": production_config_issues(settings),
        "required_external_evidence": [
            "APPROVED_DEPLOYMENT_TARGET_AND_TLS",
            "OFFSITE_ENCRYPTED_BACKUPS_AND_PITR_POLICY",
            "APPROVED_RETENTION_RPO_RTO_AND_SCHEDULE",
            "PRODUCTION_LIKE_RESTORE_AND_LOAD_TEST",
            "PHYSICAL_DEVICE_UAT_AND_OWNER_ACCEPTANCE",
            "M8_SECURITY_RISK_DECISION",
            "DURABLE_LOG_COLLECTION_ALERT_ROUTING_AND_CLIENT_QUEUE_OBSERVABILITY",
        ],
    }
    engine = None
    try:
        engine = create_engine(
            settings.database_url.get_secret_value(), connect_args={"connect_timeout": 10}
        )
        with engine.connect() as db:
            role = (
                db.execute(
                    text(
                        "SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication "
                        "FROM pg_roles WHERE rolname=current_user"
                    )
                )
                .mappings()
                .one()
            )
            result["database"] = {
                "connected": True,
                "migration_head": db.scalar(text("SELECT version_num FROM alembic_version")),
                "application_role_elevated": any(role.values()),
                "tls_in_use": bool(
                    db.scalar(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"))
                ),
                "audit_write_privileges": {
                    p: db.scalar(
                        text("SELECT has_table_privilege(current_user,'audit_logs',:p)"), {"p": p}
                    )
                    for p in ("UPDATE", "DELETE", "TRUNCATE")
                },
            }
            states = {"NORMAL": 0, "STALE": 0, "LOST": 0}
            lag = []
            now = datetime.now(UTC)
            for row in db.execute(
                text(
                    "SELECT s.gps_at,s.server_received_at,s.backend_received_at FROM vehicles v "
                    "LEFT JOIN gps_snapshots s ON s.vehicle_id=v.id "
                    "WHERE v.traccar_device_id IS NOT NULL"
                )
            ).mappings():
                states[freshness(row["gps_at"], row["server_received_at"], now)] += 1
                if (
                    row["gps_at"]
                    and row["backend_received_at"]
                    and row["backend_received_at"] >= row["gps_at"]
                ):
                    lag.append((row["backend_received_at"] - row["gps_at"]).total_seconds() * 1000)
            result["gps"] = {
                "mapped_vehicle_snapshot_states": states,
                "latest_snapshot_ingest_lag_p95_ms": p95(lag),
                "lag_samples": len(lag),
                "scope": "Latest stored snapshots; not a production time-series latency test",
            }
    except Exception:
        result["database"] = {"connected": False, "error": "UNAVAILABLE_DETAILS_WITHHELD"}
    finally:
        if engine is not None:
            engine.dispose()
    contract = root / "openapi/m8.openapi.json"
    if not contract.exists():
        contract = root / "openapi/m7.openapi.json"
    allowed = set(json.loads(contract.read_text(encoding="utf-8"))["paths"])
    if log:
        with log.open(encoding="utf-8-sig") as lines:
            result["observations"] = summarize_logs(lines, allowed)
    else:
        result["observations"] = summarize_logs([], allowed)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path)
    parser.add_argument(
        "--output", type=Path, default=root / "artifacts/m8-operational-review.json"
    )
    parser.add_argument("--require-production-ready", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts"):
        raise ValueError("Review output must stay in ignored artifacts")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = review(args.log)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if args.require_production_ready and not report["production_ready"]:
        sys.exit(1)
