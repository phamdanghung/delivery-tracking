"""Durable, actor-scoped offline action receipts."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE driver_action_receipts (
      actor_user_id uuid NOT NULL REFERENCES users(id),
      client_action_id uuid NOT NULL,
      command_hash text NOT NULL,
      response_status integer NOT NULL,
      response_json jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(actor_user_id,client_action_id)
    )""")
    op.execute("""CREATE TABLE stop_geofence_state (
      stop_id uuid PRIMARY KEY REFERENCES trip_stops(id) ON DELETE CASCADE,
      blocked boolean NOT NULL DEFAULT false,
      last_gps_at timestamptz NOT NULL,
      corrected_at timestamptz
    )""")


def downgrade() -> None:
    op.drop_table("stop_geofence_state")
    op.drop_table("driver_action_receipts")
