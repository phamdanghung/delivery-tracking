"""M2 stop attempt status and driver redelivery proposals; preserve baseline."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE trip_stops ADD COLUMN status delivery_status")
    op.execute("""UPDATE trip_stops s SET status=d.status FROM deliveries d
                  WHERE s.delivery_id=d.id""")
    op.execute("ALTER TABLE trip_stops ALTER COLUMN status SET NOT NULL")
    op.execute("ALTER TABLE trip_stops ALTER COLUMN status SET DEFAULT 'PLANNED'")
    op.execute("""CREATE TABLE delivery_reschedule_proposals (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        delivery_id uuid NOT NULL REFERENCES deliveries(id),
        failure_event_id uuid NOT NULL REFERENCES delivery_status_events(id),
        proposed_by uuid NOT NULL REFERENCES users(id),
        commitment_type commitment_type NOT NULL, scheduled_date date NOT NULL,
        appointment_at timestamptz, window_start timestamptz, window_end timestamptz,
        deadline_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
        confirmed_by uuid REFERENCES users(id), confirmed_at timestamptz,
        CHECK ((commitment_type <> 'FIXED_TIME') OR appointment_at IS NOT NULL),
        CHECK ((commitment_type <> 'TIME_WINDOW') OR
          (window_start IS NOT NULL AND window_end IS NOT NULL AND window_start <= window_end)),
        CHECK ((commitment_type <> 'BEFORE_DEADLINE') OR deadline_at IS NOT NULL),
        CHECK ((confirmed_by IS NULL) = (confirmed_at IS NULL))
    )""")
    op.execute("""CREATE INDEX idx_reschedule_delivery
                  ON delivery_reschedule_proposals(delivery_id, created_at)""")
    op.execute("CREATE INDEX idx_trip_stops_delivery ON trip_stops(delivery_id)")


def downgrade() -> None:
    op.execute("DROP INDEX idx_trip_stops_delivery")
    op.execute("DROP TABLE delivery_reschedule_proposals")
    op.execute("ALTER TABLE trip_stops DROP COLUMN status")
