"""Install the supplied V1.0 schema without changing its business contract."""

from pathlib import Path

from alembic import context, op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = Path(__file__).resolve().parents[4] / "db/migrations/0001_baseline.sql"
    sql = source.read_text(encoding="utf-8-sig")
    if context.is_offline_mode():
        op.execute(sql)
    else:
        op.get_bind().exec_driver_sql(sql)


def downgrade() -> None:
    # Reverse dependency order. Extensions may be shared and are intentionally retained.
    tables = (
        "audit_logs",
        "safety_alerts",
        "vehicle_documents",
        "maintenance_events",
        "maintenance_rules",
        "expenses",
        "fuel_entries",
        "fuel_profiles",
        "tracking_tokens",
        "pod_photos",
        "delivery_status_events",
        "trip_stops",
        "trips",
        "deliveries",
        "driver_profiles",
        "vehicles",
        "users",
    )
    for table in tables:
        op.execute(f"DROP TABLE {table}")
    for enum in ("trip_status", "commitment_type", "delivery_status", "user_role"):
        op.execute(f"DROP TYPE {enum}")
