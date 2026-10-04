"""Add M1 sessions and business GPS snapshots without rewriting baseline 0001."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE auth_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id),
            family_id uuid NOT NULL,
            refresh_hash text NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id);
        CREATE INDEX idx_auth_sessions_family ON auth_sessions(family_id);
        CREATE TABLE gps_snapshots (
            vehicle_id uuid PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
            traccar_device_id bigint NOT NULL,
            position_id bigint NOT NULL,
            latitude double precision NOT NULL CHECK(latitude BETWEEN -90 AND 90),
            longitude double precision NOT NULL CHECK(longitude BETWEEN -180 AND 180),
            speed_kmh double precision NOT NULL CHECK(speed_kmh >= 0),
            course double precision NOT NULL CHECK(course >= 0 AND course <= 360),
            gps_at timestamptz NOT NULL,
            server_received_at timestamptz NOT NULL,
            backend_received_at timestamptz NOT NULL DEFAULT now(),
            acc boolean,
            engine_state text NOT NULL CHECK(engine_state IN ('MOVING','IDLING','PARKED','UNKNOWN'))
        );
        CREATE TABLE vehicle_state_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            vehicle_id uuid NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
            engine_state text NOT NULL
                CHECK(engine_state IN ('MOVING','IDLING','PARKED','UNKNOWN')),
            started_at timestamptz NOT NULL,
            ended_at timestamptz,
            CHECK(ended_at IS NULL OR ended_at >= started_at)
        );
        CREATE UNIQUE INDEX idx_vehicle_state_open ON vehicle_state_events(vehicle_id)
            WHERE ended_at IS NULL;
        CREATE INDEX idx_vehicle_state_history ON vehicle_state_events(vehicle_id,started_at);
    """)


def downgrade() -> None:
    op.execute(
        "DROP TABLE vehicle_state_events; DROP TABLE gps_snapshots; DROP TABLE auth_sessions"
    )
