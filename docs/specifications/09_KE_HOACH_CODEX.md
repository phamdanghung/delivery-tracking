# 09 - KẾ HOẠCH TRIỂN KHAI CHO CODEX

## Quy tắc giao việc
Không yêu cầu Codex “làm toàn bộ hệ thống” trong một prompt. Mỗi milestone phải có branch/PR, tests và tiêu chí thoát.

### M0 - Khởi tạo repository
- monorepo: `/apps/admin-web`, `/apps/driver-mobile`, `/apps/api`, `/packages/shared`, `/infra`, `/docs`.
- Docker Compose: postgres/postgis, redis, minio, traccar, api.
- CI lint/typecheck/test.

### M1 - Auth + Fleet + GPS
Users/RBAC, vehicle/device mapping, Traccar adapter, live map, history, ACC state, audit base.

### M2 - Delivery + Trip + State machine
Tạo đơn, 3 kiểu hẹn, trip, stops, phân xe/tài xế, transitions, giao lại.

### M3 - Route optimization
RoutingProvider, geocoding, matrix, OR-Tools, objective đúng giờ -> km -> time, cảnh báo infeasible, route approval.

### M4 - Driver app + offline
Trip today, stop detail, navigation deep-link, outbox/idempotency, geofence events.

### M5 - POD
Chụp ảnh, upload private object storage, metadata, điều kiện DELIVERED.

### M6 - Customer tracking
Tracking token, public page, exact GPS, ETA, 1-hour expiry, copy link.

### M7 - Fuel/Expense/Maintenance/Safety
Fuel profiles, formula, 15% alert; expenses; maintenance per vehicle; documents; outside-hours 18:00-07:30.

### M8 - Reports + hardening + UAT
Reports, backups, monitoring, performance, security test, acceptance suite, deployment runbook.

## Mẫu prompt cho Codex
Mỗi task phải ghi: Goal; requirement IDs; files được phép sửa; API/data contract; acceptance tests; auth rules; non-goals; definition of done.

## Stop condition
Codex phải dừng và hỏi khi cần thay đổi nghiệp vụ V1.1, thay đổi breaking API/schema đã khóa, phát sinh nhà cung cấp API trả phí chưa được duyệt, hoặc yêu cầu chức năng remote immobilization.
