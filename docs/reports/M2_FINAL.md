# M2 FINAL

Ngày: 06/10/2026. Branch: `codex/m2-delivery-trips`. Trạng thái: **FAIL — chỉ còn security exception chưa được phê duyệt cho M2**. Các kiểm tra kỹ thuật và CI remote PASS.

## 1. Phần đã triển khai

- ROUT-01/05, POD-03, ASSET-01; áp dụng DEC-025–028, đối chiếu `M2_SCOPE.md` và `M2_TRACEABILITY.csv`.
- Nhập/sửa đơn trước lập chuyến, nháp Zalo chỉ gợi ý, ba kiểu hẹn, lọc danh sách, chi tiết/timeline/audit; không tự geocode.
- Xe/tài xế/stops theo thứ tự chọn, chỉ lưu DRAFT; không duyệt/xuất hoặc ETA giả. Thiếu điểm công ty báo cấu hình, yêu cầu điểm thay thế hợp lệ. Quá tải chỉ warning.
- Hủy CREATED/PLANNED/ASSIGNED chỉ ADMIN/DISPATCHER, lý do/audit bắt buộc. Không sửa ARRIVED ngược.
- State/RBAC/stale-write/concurrency; DRIVER chỉ truy cập chuyến đã duyệt của mình, chỉ đề xuất giao lại; operator xác nhận mới RESCHEDULED. DELIVERED yêu cầu POD tồn tại trên private storage thật; upload thuộc M5.

## 2. File/migration/API chính

- `apps/api/app/deliveries.py`, `delivery_schemas.py`; `0003_m2_delivery_trip.py` (revision `0003`, parent `0002`): TripStop.status và delivery_reschedule_proposals.
- `/api/v1/deliveries`, detail/edit/status/reschedule; `/api/v1/trips`, config/detail/start. Start không nhận DRAFT, không expose qua web BFF; không có API duyệt M2.
- `openapi/m2.openapi.json`; baseline SQL/OpenAPI và snapshot M1 giữ nguyên, test tương thích M1.
- Web `/deliveries` và `/trips`, reuse auth/BFF/sidebar/tokens M1; `.env.example`/Compose thêm COMPANY_LATITUDE/LONGITUDE; CI mở rộng theo source M2.
- Không đổi package/lockfile, Expo SDK, React Native, mobile source hoặc kiến trúc. Các DEC cũ giữ nguyên.

## 3. Test/build/Docker

| Kiểm tra | Kết quả / bằng chứng local |
|---|---|
| Backend full suite | 55 PASS, không fail/skip; `artifacts/m2-database-tests.log` |
| Real PostGIS migration | Dev upgrade 0003; test DB downgrade base/upgrade head, rerun 13 integration PASS; cùng log |
| Shared Node tests | 7 PASS; `artifacts/m2-node-tests.log` |
| Ruff/format/mypy | PASS, từ apps/api; không broad-format baseline |
| Web lint/typecheck/build | PASS, cả sau sửa retry form; 18 server traces, 0 braces/node-forge references |
| Docker | API/web rebuilt, stack up --wait; postgres/redis/minio/traccar/api/admin-web healthy, minio-init exit 0; `artifacts/m2-stack-final.log` |
| Health | API live/ready, web 200; DB/redis/storage/Traccar true, Redis PONG; MinIO signed write/read PASS, anonymous 403; `artifacts/m2-stack-health.json` |
| Browser real DB | Zalo/create/three types, empty/loading, draft/overload/missing points, cancel reason/audit, proposal confirm, conflict 409/retry/data retained, DRIVER denied; screenshots `artifacts/m2-ui-*.png` |
| Responsive | 360px form, 768px table: document width equals scroll width; screenshots inspected |
| npm ci/mobile | Remote CI M2 clean install và Android/iOS export PASS; 578/580 sources sạch; local reuse M1 do source/lock không đổi |

UI test server uses its own real PostGIS database on loopback 18000/13000; fixtures are labelled simulated. Temporary DB/credentials removed after testing. Production/dev application data is not used for fixture state promotion.

Docker Desktop dừng ở phiên cuối và gặp socket runtime stale (`sailor-ingest.sock`, `engine.sock`). Đã sao lưu các thư mục socket tạm, khởi động lại Desktop; **Engine 29.7.2**, Compose up --wait và health sâu **PASS** sau phục hồi (`artifacts/m2-stack-restored.log`, `m2-stack-restored-health.log`). Không reset/factory reset, không xóa volumes/WSL/database vận hành. Database UI riêng `fleet_m2_ui_6576e996b999` đã được kiểm tra đúng fixture trước khi drop, credentials tạm đã xóa.

## 4. CI remote

Source SHA `a499916d3ff65cb54d36f908a6071fd53ab97f67`: **PASS**, [run 37386191987](https://github.com/phamdanghung/delivery-tracking/actions/runs/37386191987), frontend/backend completed/success. Đã tải và đọc log thực tế `artifacts/m2-ci-frontend.log` và `m2-ci-backend.log`: npm ci 765 packages, audit 19 high hiện rõ; shared 7 PASS; web build và 18 traces sạch; Android/iOS export và 578/580 sources sạch; backend 55 PASS, downgrade/upgrade và integration rerun 13 PASS. Local tests không thay bằng chứng CI.

[Draft PR #1](https://github.com/phamdanghung/delivery-tracking/pull/1) so với branch M1; chưa merge. Commit tiếp theo chỉ cập nhật tài liệu nghiệm thu/decision nếu được phê duyệt.

## 5. Điểm chưa xác minh / giới hạn

- APK/IPA, thiết bị/GPS vật lý, production chưa nghiệm thu; export bundle không thay native build.
- Optimization/ETA/approval M3, offline/geofence/correction M4, upload POD M5, customer tracking M6 chưa triển khai theo phạm vi khóa.
- Tọa độ công ty chưa được cung cấp; hệ thống báo thiếu cấu hình và chặn lưu thiếu điểm. Không đưa tọa độ giả vào ENV.

## 6. Security / quyết định cần chủ dự án

Audit hiện tại: 19 high, 0 critical, cùng hai root advisory `braces GHSA-vfj7-8cjw-p6xm` và `node-forge GHSA-86w9-cpqp-85rv`; tooling/transitive Expo/Metro, chưa có bản vá tương thích tại lần rà soát. M2 không đổi dependency; web runtime gate 18 traces không có hai package. CI M2 đã kiểm tra Android/iOS 578/580 sources sạch.

DEC-024 chỉ cho M1 development/local/CI, **không áp dụng M2 hoặc production**. Chưa tự nhận exception M2, chưa coi advisory đã vá. Giữ audit và runtime gates, repo/config/cert tin cậy, Metro/Compose loopback, không force fix/downgrade/suppress. Cần chủ dự án quyết định riêng nếu chấp nhận tạm thời cho M2; review muộn nhất 02/11/2026 hoặc trước production, mốc sớm hơn; patch sớm cần full verification, runtime surface thay đổi phải dừng đánh giá.

## 7. Kết luận

**FAIL tại thời điểm chốt báo cáo**: source/test/migration/build/export/Docker/health/CI đều PASS; chưa có phê duyệt chấp nhận tạm thời hai advisory riêng cho M2. Đây là security gate chưa được chủ dự án quyết định, không phải test FAIL. Không tự suy rộng DEC-024, không tự kết luận PASS WITH CONDITIONS. Chờ quyết định mới; không chuyển M3.
