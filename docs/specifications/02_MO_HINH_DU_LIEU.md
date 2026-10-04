# 02 - MÔ HÌNH DỮ LIỆU

## Thực thể chính
### User
`id, full_name, phone, email, password_hash, role, is_active, created_at`

### Vehicle
`id, plate_no, name, vehicle_type, max_weight_kg, max_volume_m3, traccar_device_id, status`

### DriverProfile
`id, user_id, phone, active`

### Delivery
`id, code, recipient_name, recipient_phone, address_text, latitude, longitude, time_commitment_type, appointment_at, window_start, window_end, deadline_at, weight_kg, volume_m3, status, notes, scheduled_date`

`time_commitment_type` gồm:
- `FIXED_TIME` - giờ cố định.
- `TIME_WINDOW` - khung giờ.
- `BEFORE_DEADLINE` - giao trước một mốc.

### Trip
`id, trip_date, vehicle_id, driver_id, start_lat, start_lon, end_lat, end_lon, status, planned_distance_m, planned_duration_s`

### TripStop
`id, trip_id, delivery_id, sequence_no, planned_arrival_at, eta_at, arrived_at, completed_at, status`

### DeliveryStatusEvent
Lưu lịch sử trạng thái bất biến: `delivery_id, from_status, to_status, event_time, actor_user_id, source, reason, lat, lon`.

### PodPhoto
`delivery_id, object_key, captured_at, uploaded_at, latitude, longitude, sha256, sync_id`.

### TrackingToken
`delivery_id, token_hash, issued_at, expires_at, revoked_at`. Hết hiệu lực 1 giờ sau khi giao thành công.

### FuelProfile
Định mức riêng theo xe: `driving_l_per_100km, idling_l_per_hour, effective_from, effective_to`.

### FuelEntry
`vehicle_id, trip_id, liters, amount, receipt_object_key, filled_at, latitude, longitude, estimated_liters, variance_pct, alert_flag`. Cảnh báo khi `variance_pct > 15`.

### Expense
`trip_id, type, amount, receipt_object_key, note, incurred_at`.

### MaintenanceRule
Cấu hình riêng từng xe: `vehicle_id, task_type, interval_km, interval_days, lead_km, lead_days`.

### MaintenanceEvent
`vehicle_id, task_type, service_date, odometer_km, note`.

### VehicleDocument
`vehicle_id, doc_type, expiry_date, lead_days`.

### SafetyAlert
`vehicle_id, type, event_time, severity, payload_json, acknowledged_by, acknowledged_at`. Ngoài giờ mặc định 18:00-07:30.

### AuditLog
`actor_user_id, action, resource_type, resource_id, before_json, after_json, reason, created_at, request_id`.

## Quan hệ chính
Vehicle 1-N Trip; Driver 1-N Trip; Trip 1-N TripStop; Delivery 1-N status events; Delivery 0-N POD photos; Delivery 0-N tracking tokens.
