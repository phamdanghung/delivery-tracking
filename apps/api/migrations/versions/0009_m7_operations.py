"""M7 operational records and versioned reconciliation; DEC-047/048/049."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE EXTENSION IF NOT EXISTS btree_gist;
      ALTER TABLE fuel_profiles ADD CONSTRAINT fuel_profile_rates
        CHECK(driving_l_per_100km >= 0 AND idling_l_per_hour >= 0),
        ADD CONSTRAINT fuel_profile_dates
          CHECK(effective_to IS NULL OR effective_to>effective_from),
        ADD CONSTRAINT fuel_profile_overlap EXCLUDE USING gist
          (vehicle_id WITH =, daterange(effective_from,effective_to,'[)') WITH &&);
      ALTER TABLE fuel_entries ADD COLUMN note text,
        ADD COLUMN deleted_at timestamptz,
        ADD CONSTRAINT fuel_entry_positive CHECK(liters>0 AND (amount IS NULL OR amount>=0));
      CREATE TABLE fuel_reconciliations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        vehicle_id uuid NOT NULL REFERENCES vehicles(id),
        from_at timestamptz NOT NULL, to_at timestamptz NOT NULL,
        status text NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','FINAL')),
        created_by uuid NOT NULL REFERENCES users(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        CHECK(from_at<to_at),
        EXCLUDE USING gist (vehicle_id WITH =, tstzrange(from_at,to_at,'[)') WITH &&)
          WHERE (status='FINAL')
      );
      CREATE TABLE fuel_reconciliation_versions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        reconciliation_id uuid NOT NULL REFERENCES fuel_reconciliations(id),
        version integer NOT NULL CHECK(version>0),
        computed_at timestamptz NOT NULL DEFAULT now(),
        computed_by uuid NOT NULL REFERENCES users(id),
        reason text NOT NULL,
        result_json jsonb NOT NULL,
        UNIQUE(reconciliation_id,version)
      );
      ALTER TABLE maintenance_rules ADD COLUMN baseline_date date,
        ADD COLUMN baseline_odometer_km numeric(12,1),
        ADD COLUMN baseline_source text;
      ALTER TABLE maintenance_events ADD COLUMN rule_id uuid REFERENCES maintenance_rules(id),
        ADD COLUMN created_by uuid REFERENCES users(id),
        ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(),
        ADD COLUMN cost numeric(14,2), ADD COLUMN receipt_object_key text,
        ADD COLUMN odometer_source text;
      CREATE TABLE vehicle_odometer_readings (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        vehicle_id uuid NOT NULL REFERENCES vehicles(id),
        odometer_km numeric(12,1) NOT NULL CHECK(odometer_km>=0),
        observed_at timestamptz NOT NULL, source text NOT NULL CHECK(source IN ('TRACCAR','ADMIN')),
        reason text NOT NULL, created_by uuid REFERENCES users(id),
        created_at timestamptz NOT NULL DEFAULT now(), source_position_id bigint,
        UNIQUE(vehicle_id,source_position_id)
      );
      CREATE TABLE expense_receipts (
        id uuid PRIMARY KEY, trip_id uuid NOT NULL REFERENCES trips(id),
        created_by uuid NOT NULL REFERENCES users(id), client_action_id uuid NOT NULL,
        request_hash text NOT NULL, object_key text NOT NULL UNIQUE,
        object_version text NOT NULL, sha256 text NOT NULL,
        original_sha256 text NOT NULL, content_type text NOT NULL, size_bytes integer NOT NULL,
        source text NOT NULL CHECK(source IN ('CAMERA_CAPTURED','ALBUM_SELECTED')),
        captured_at timestamptz NOT NULL, uploaded_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(created_by,client_action_id)
      );
      ALTER TABLE expenses ADD COLUMN client_action_id uuid,
        ADD COLUMN request_hash text,
        ADD COLUMN receipt_id uuid REFERENCES expense_receipts(id),
        ADD CONSTRAINT expense_amount CHECK(amount>=0),
        ADD CONSTRAINT expense_action UNIQUE(created_by,client_action_id);
      CREATE TABLE vehicle_receipts (
        id uuid PRIMARY KEY, vehicle_id uuid NOT NULL REFERENCES vehicles(id),
        kind text NOT NULL CHECK(kind IN ('FUEL','MAINTENANCE')),
        created_by uuid NOT NULL REFERENCES users(id), client_action_id uuid NOT NULL,
        request_hash text NOT NULL, object_key text NOT NULL UNIQUE, object_version text NOT NULL,
        sha256 text NOT NULL, original_sha256 text NOT NULL,
        content_type text NOT NULL, size_bytes integer NOT NULL,
        source text NOT NULL CHECK(source IN ('CAMERA_CAPTURED','ALBUM_SELECTED')),
        captured_at timestamptz NOT NULL, uploaded_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(created_by,client_action_id)
      );
      ALTER TABLE fuel_entries ADD COLUMN receipt_id uuid REFERENCES vehicle_receipts(id),
        ADD COLUMN client_action_id uuid, ADD COLUMN request_hash text,
        ADD CONSTRAINT fuel_entry_action UNIQUE(created_by,client_action_id);
      ALTER TABLE maintenance_events ADD COLUMN receipt_id uuid REFERENCES vehicle_receipts(id),
        ADD COLUMN client_action_id uuid, ADD COLUMN request_hash text,
        ADD CONSTRAINT maintenance_event_action UNIQUE(created_by,client_action_id);
      CREATE TABLE safety_configs (
        vehicle_id uuid PRIMARY KEY REFERENCES vehicles(id),
        speed_limit_kmh numeric(8,3) CHECK(speed_limit_kmh>0),
        outside_hours_enabled boolean NOT NULL DEFAULT true,
        updated_by uuid NOT NULL REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE safety_exceptions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        vehicle_id uuid NOT NULL REFERENCES vehicles(id),
        type text NOT NULL CHECK(type IN ('SPEEDING','OUTSIDE_HOURS')),
        from_at timestamptz NOT NULL, to_at timestamptz NOT NULL, reason text NOT NULL,
        created_by uuid NOT NULL REFERENCES users(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        deleted_at timestamptz, CHECK(from_at<to_at)
      );
      ALTER TABLE safety_alerts ADD COLUMN status text NOT NULL DEFAULT 'NEW'
        CHECK(status IN ('NEW','SEEN','RESOLVED')),
        ADD COLUMN seen_by uuid REFERENCES users(id), ADD COLUMN seen_at timestamptz,
        ADD COLUMN resolved_by uuid REFERENCES users(id), ADD COLUMN resolved_at timestamptz,
        ADD COLUMN resolution_reason text, ADD COLUMN incident_ended_at timestamptz,
        ADD COLUMN last_event_at timestamptz, ADD COLUMN source_position_id bigint;
      UPDATE safety_alerts SET status='SEEN',seen_by=acknowledged_by,seen_at=acknowledged_at
        WHERE acknowledged_at IS NOT NULL;
      CREATE UNIQUE INDEX safety_active_incident ON safety_alerts(vehicle_id,type)
        WHERE incident_ended_at IS NULL AND source_position_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
      DROP INDEX safety_active_incident;
      ALTER TABLE safety_alerts DROP COLUMN status, DROP COLUMN seen_by, DROP COLUMN seen_at,
        DROP COLUMN resolved_by, DROP COLUMN resolved_at, DROP COLUMN resolution_reason,
        DROP COLUMN incident_ended_at, DROP COLUMN last_event_at, DROP COLUMN source_position_id;
      DROP TABLE safety_exceptions; DROP TABLE safety_configs;
      ALTER TABLE expenses DROP COLUMN client_action_id, DROP COLUMN request_hash,
        DROP COLUMN receipt_id, DROP CONSTRAINT expense_amount, DROP CONSTRAINT expense_action;
      DROP TABLE expense_receipts;
      ALTER TABLE maintenance_events DROP COLUMN receipt_id, DROP COLUMN client_action_id,
        DROP COLUMN request_hash, DROP CONSTRAINT maintenance_event_action;
      ALTER TABLE fuel_entries DROP COLUMN receipt_id, DROP COLUMN client_action_id,
        DROP COLUMN request_hash, DROP CONSTRAINT fuel_entry_action;
      DROP TABLE vehicle_receipts;
      DROP TABLE vehicle_odometer_readings;
      ALTER TABLE maintenance_events DROP COLUMN rule_id, DROP COLUMN created_by,
        DROP COLUMN created_at, DROP COLUMN cost, DROP COLUMN receipt_object_key,
        DROP COLUMN odometer_source;
      ALTER TABLE maintenance_rules DROP COLUMN baseline_date,
        DROP COLUMN baseline_odometer_km, DROP COLUMN baseline_source;
      DROP TABLE fuel_reconciliation_versions; DROP TABLE fuel_reconciliations;
      ALTER TABLE fuel_entries DROP COLUMN note, DROP COLUMN deleted_at,
        DROP CONSTRAINT fuel_entry_positive;
      ALTER TABLE fuel_profiles DROP CONSTRAINT fuel_profile_overlap,
        DROP CONSTRAINT fuel_profile_dates, DROP CONSTRAINT fuel_profile_rates;
    """)
