-- PostgreSQL 16 + PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('ADMIN','DISPATCHER','DRIVER');
CREATE TYPE delivery_status AS ENUM ('CREATED','PLANNED','ASSIGNED','EN_ROUTE','ARRIVED','DELIVERING','DELIVERED','FAILED','RESCHEDULED','CANCELLED');
CREATE TYPE commitment_type AS ENUM ('FIXED_TIME','TIME_WINDOW','BEFORE_DEADLINE');
CREATE TYPE trip_status AS ENUM ('DRAFT','PLANNED','ACTIVE','COMPLETED','CANCELLED');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL, phone text, email text UNIQUE, password_hash text NOT NULL,
  role user_role NOT NULL, is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vehicles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plate_no text NOT NULL UNIQUE, name text, vehicle_type text,
  max_weight_kg numeric(12,2), max_volume_m3 numeric(12,3), traccar_device_id bigint UNIQUE,
  status text NOT NULL DEFAULT 'ACTIVE', created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE driver_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL UNIQUE REFERENCES users(id), active boolean NOT NULL DEFAULT true
);

CREATE TABLE deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL UNIQUE,
  recipient_name text NOT NULL, recipient_phone text NOT NULL, address_text text NOT NULL,
  location geography(Point,4326), commitment_type commitment_type, appointment_at timestamptz,
  window_start timestamptz, window_end timestamptz, deadline_at timestamptz,
  weight_kg numeric(12,2), volume_m3 numeric(12,3), status delivery_status NOT NULL DEFAULT 'CREATED',
  scheduled_date date, notes text, created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((commitment_type <> 'FIXED_TIME') OR appointment_at IS NOT NULL),
  CHECK ((commitment_type <> 'TIME_WINDOW') OR (window_start IS NOT NULL AND window_end IS NOT NULL AND window_start <= window_end)),
  CHECK ((commitment_type <> 'BEFORE_DEADLINE') OR deadline_at IS NOT NULL)
);
CREATE INDEX idx_deliveries_location ON deliveries USING gist(location);
CREATE INDEX idx_deliveries_status_date ON deliveries(status, scheduled_date);

CREATE TABLE trips (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trip_date date NOT NULL, vehicle_id uuid REFERENCES vehicles(id),
  driver_id uuid REFERENCES driver_profiles(id), start_location geography(Point,4326), end_location geography(Point,4326),
  status trip_status NOT NULL DEFAULT 'DRAFT', planned_distance_m integer, planned_duration_s integer,
  created_by uuid REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE trip_stops (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trip_id uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  delivery_id uuid NOT NULL REFERENCES deliveries(id), sequence_no integer NOT NULL,
  planned_arrival_at timestamptz, eta_at timestamptz, arrived_at timestamptz, completed_at timestamptz,
  UNIQUE(trip_id, sequence_no), UNIQUE(trip_id, delivery_id)
);

CREATE TABLE delivery_status_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), delivery_id uuid NOT NULL REFERENCES deliveries(id),
  from_status delivery_status, to_status delivery_status NOT NULL, event_time timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid REFERENCES users(id), source text NOT NULL, reason text,
  location geography(Point,4326), request_id text
);
CREATE INDEX idx_delivery_events_delivery_time ON delivery_status_events(delivery_id,event_time);

CREATE TABLE pod_photos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), delivery_id uuid NOT NULL REFERENCES deliveries(id),
  object_key text NOT NULL, captured_at timestamptz NOT NULL, uploaded_at timestamptz,
  location geography(Point,4326), sha256 text, sync_id text UNIQUE, created_by uuid REFERENCES users(id)
);

CREATE TABLE tracking_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), delivery_id uuid NOT NULL REFERENCES deliveries(id),
  token_hash text NOT NULL UNIQUE, issued_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL, revoked_at timestamptz
);

CREATE TABLE fuel_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), vehicle_id uuid NOT NULL REFERENCES vehicles(id),
  driving_l_per_100km numeric(8,3) NOT NULL, idling_l_per_hour numeric(8,3) NOT NULL,
  effective_from date NOT NULL, effective_to date
);

CREATE TABLE fuel_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), vehicle_id uuid NOT NULL REFERENCES vehicles(id), trip_id uuid REFERENCES trips(id),
  liters numeric(10,3) NOT NULL, amount numeric(14,2), receipt_object_key text, filled_at timestamptz NOT NULL,
  location geography(Point,4326), estimated_liters numeric(10,3), variance_pct numeric(8,3),
  alert_flag boolean NOT NULL DEFAULT false, created_by uuid REFERENCES users(id)
);

CREATE TABLE expenses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), trip_id uuid NOT NULL REFERENCES trips(id), type text NOT NULL,
  amount numeric(14,2) NOT NULL, receipt_object_key text, note text, incurred_at timestamptz NOT NULL, created_by uuid REFERENCES users(id)
);

CREATE TABLE maintenance_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), vehicle_id uuid NOT NULL REFERENCES vehicles(id), task_type text NOT NULL,
  interval_km integer, interval_days integer, lead_km integer, lead_days integer, active boolean NOT NULL DEFAULT true
);
CREATE TABLE maintenance_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), vehicle_id uuid NOT NULL REFERENCES vehicles(id), task_type text NOT NULL,
  service_date date NOT NULL, odometer_km numeric(12,1), note text
);
CREATE TABLE vehicle_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), vehicle_id uuid NOT NULL REFERENCES vehicles(id), doc_type text NOT NULL,
  expiry_date date NOT NULL, lead_days integer NOT NULL DEFAULT 30
);

CREATE TABLE safety_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), vehicle_id uuid NOT NULL REFERENCES vehicles(id), type text NOT NULL,
  event_time timestamptz NOT NULL, severity text NOT NULL DEFAULT 'WARNING', payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  acknowledged_by uuid REFERENCES users(id), acknowledged_at timestamptz
);

CREATE TABLE audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor_user_id uuid REFERENCES users(id), action text NOT NULL,
  resource_type text NOT NULL, resource_id text NOT NULL, before_json jsonb, after_json jsonb, reason text,
  request_id text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type,resource_id,created_at);
