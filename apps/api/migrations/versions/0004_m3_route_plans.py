"""M3 confirmed departure and immutable optimization input/result snapshots."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE trips ADD COLUMN planned_departure_at timestamptz")
    op.execute("""CREATE TABLE trip_route_plans (
        id uuid PRIMARY KEY, trip_id uuid NOT NULL REFERENCES trips(id),
        input_fingerprint text NOT NULL, input_json jsonb NOT NULL, result_json jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        created_by uuid NOT NULL REFERENCES users(id),
        approved_at timestamptz, approved_by uuid REFERENCES users(id),
        CHECK ((approved_at IS NULL) = (approved_by IS NULL))
    )""")
    op.execute("CREATE INDEX idx_route_plans_trip ON trip_route_plans(trip_id,created_at DESC,id)")


def downgrade() -> None:
    op.execute("DROP TABLE trip_route_plans")
    op.execute("ALTER TABLE trips DROP COLUMN planned_departure_at")
