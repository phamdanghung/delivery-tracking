"""M6 tracking bound to a delivery attempt; preserve legacy links as invalid."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE tracking_tokens ALTER COLUMN expires_at DROP NOT NULL,
      ADD COLUMN trip_stop_id uuid REFERENCES trip_stops(id),
      ADD COLUMN vehicle_id uuid REFERENCES vehicles(id),
      ADD COLUMN created_by uuid REFERENCES users(id);
      CREATE INDEX idx_tracking_attempt ON tracking_tokens(trip_stop_id);
    """)


def downgrade() -> None:
    # Retained links cannot regain validity by downgrading to a legacy schema.
    op.execute("""UPDATE tracking_tokens SET expires_at=COALESCE(expires_at,now()),
      revoked_at=COALESCE(revoked_at,now());
      DROP INDEX idx_tracking_attempt;
      ALTER TABLE tracking_tokens DROP COLUMN trip_stop_id, DROP COLUMN vehicle_id,
      DROP COLUMN created_by, ALTER COLUMN expires_at SET NOT NULL;
    """)
