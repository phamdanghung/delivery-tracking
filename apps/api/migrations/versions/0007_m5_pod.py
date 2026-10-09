"""M5 POD attempt binding and immutable upload provenance."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical POD remains readable; never guess its attempt or source.
    op.execute("""ALTER TABLE pod_photos
      ADD COLUMN trip_stop_id uuid REFERENCES trip_stops(id),
      ADD COLUMN source text CHECK (source IN ('CAMERA_CAPTURED','ALBUM_SELECTED')),
      ADD COLUMN location_status text CHECK (location_status IN ('VERIFIED','LOCATION_UNVERIFIED')),
      ADD COLUMN gps_fix_at timestamptz,
      ADD COLUMN gps_freshness text,
      ADD COLUMN location_reason text,
      ADD COLUMN original_sha256 text,
      ADD COLUMN request_hash text,
      ADD COLUMN object_version text,
      ADD COLUMN content_type text,
      ADD COLUMN size_bytes bigint CHECK (size_bytes > 0);
      CREATE INDEX idx_pod_attempt ON pod_photos(trip_stop_id);
    """)


def downgrade() -> None:
    op.execute("""DROP INDEX idx_pod_attempt;
      ALTER TABLE pod_photos DROP COLUMN trip_stop_id, DROP COLUMN source,
      DROP COLUMN location_status, DROP COLUMN gps_fix_at, DROP COLUMN gps_freshness,
      DROP COLUMN location_reason, DROP COLUMN original_sha256, DROP COLUMN request_hash,
      DROP COLUMN object_version, DROP COLUMN content_type, DROP COLUMN size_bytes;
    """)
