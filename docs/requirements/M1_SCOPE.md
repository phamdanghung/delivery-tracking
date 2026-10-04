# M1 — phạm vi và quyết định triển khai

Nguồn: chỉ thị M1 của chủ dự án ngày 05/10/2026, START_HERE V1.1, nghiệp vụ V1.1, Technical Pack V1.0 và UX/UI V1.0. Nhánh: codex/m1-auth-fleet-gps. M0 giữ PASS WITH ACCEPTED RISK; chấp nhận advisory chỉ có phạm vi M0, cần kiểm tra lại attack surface trong M1.

## Đã đối chiếu trước code

M0 có schema users/vehicles/driver_profiles/trips/audit_logs nhưng chưa có auth/fleet/GPS API hoặc UI. Giữ baseline 0001 và SQL gốc. M1 thêm migration cho phiên auth và snapshot/sự kiện ACC cần truy vết, không sao chép toàn bộ GPS thô khỏi Traccar. Auth JWT ngắn hạn, refresh rotation, Argon2id, RBAC server-side. ADMIN quản trị user/xe/mapping; DISPATCHER chỉ đọc xe/GPS/history/profile, chưa cấp quyền quản trị xe mở rộng; DRIVER chỉ thông tin tài khoản của mình. ADMIN không được vô hiệu hóa ADMIN hoạt động cuối cùng.

GPS-01/02/03/04 theo kế hoạch M1: REST + WebSocket adapter Traccar thật, device mapping duy nhất, live map, lịch sử/playback/điểm dừng, km theo báo cáo Traccar. Dùng speed knots của Traccar đổi sang km/h ở biên adapter; không tự đặt ngưỡng tốc độ khác 0. ACC thiếu hoặc GPS invalid => UNKNOWN. Traccar là nguồn lịch sử GPS, backend chỉ lưu snapshot/state transitions cần truy vết. Không nối đường qua khoảng thiếu GPS >120 giây; hiển thị gap.

GPS freshness dùng tuổi vị trí GPS và thời gian Traccar server nhận, lấy giá trị cũ hơn để không biến bản tin vừa đến nhưng fix cũ thành live. NORMAL <=30 giây, STALE >30 và <=120 giây, LOST >120 giây. Giá trị null/invalid/future time không được giả là NORMAL. server_received_at (Traccar) tách backend_received_at. Khi mất upstream, trả lỗi 503 và UI giữ vị trí cuối với cảnh báo, không biến snapshot thành live.

DriverProfile liên kết User; vehicle được phân qua Trip theo nghiệp vụ V1.1, không thêm quan hệ xe cố định và không tạo workflow Trip M2. Các liên kết Trip hiện có chỉ đọc để hiển thị, nếu chưa có Trip thì ghi chưa phân xe.

## Quyết định mới của chủ dự án

- Giao lại: tài xế chỉ đề xuất; điều phối xác nhận mới hiệu lực. Ghi nhận cho M2/M4, không code reschedule trong M1.
- Safety alert NEW/SEEN/RESOLVED tách biệt. Đề xuất migration M7 thêm status, seen_by/at, resolved_by/at, giữ acknowledged_* để tương thích; không tạo migration safety ở M1 vì chưa triển khai cảnh báo M7.
- GPS thresholds ở trên thay chỗ ngưỡng chưa chốt và khác biệt UX '<30 giây'. Chỉ thị mới là nguồn đã phê duyệt; đúng 30 giây vẫn NORMAL, đúng 120 giây STALE.

## Contract và UI

Giữ OpenAPI V1.0 nguyên văn làm contract nghiệp vụ; bổ sung openapi/m1.openapi.json sinh trực tiếp từ FastAPI cho endpoint M1/schemas/status/security. Đây là phần bổ sung không breaking; các endpoint M2+ vẫn chưa triển khai. UI WEB-01/03/09/14 và quản trị xe cơ bản dùng sidebar/topbar, tokens M0, loading/empty/error/permission/stale states. Bản đồ Leaflet/OpenStreetMap cho local dev, attribution và tile policy, không mua API hoặc triển khai tối ưu tuyến. Basemap configurable; production provider cần review riêng.

## Xác minh và non-goals

Tests thật PostGIS + migration upgrade/downgrade/upgrade; auth/RBAC/vehicle/mapping/GPS/ACC/freshness/UI states/outage; Traccar REST/socket và OsmAnd feed mô phỏng có nhãn, không nghiệm thu GPS vật lý. Docker/health, npm ci/audit, lint/typecheck/build/export, backend suite và remote CI bắt buộc. Không route optimization, delivery workflow, e-POD/tracking/fuel/maintenance/remote immobilization. Không tự chuyển M2.
