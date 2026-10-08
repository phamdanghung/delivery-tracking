# M4 — Driver App / offline / geofence

Branch `codex/m4-driver-offline-geofence`, base M3 merge `8d95b1c7c08df79f24335526c9e2763a02309e29`.

Áp dụng ROUT-03/04, DEC-004/014/015/020/028, AT-05/06 và UX DRV-01/02/03/04/06/08. React Native/Expo SDK 57 hiện tại, Expo Router theo AGENTS.md; SQLite cache/outbox, SecureStore cho token, API/RBAC và GPS Traccar hiện có. Không đổi baseline M1/M2/M3 contracts; bổ sung contract M4 có phiên bản cho sync/cache cần thiết.

- Cache dữ liệu chuyến đã duyệt của chính tài xế theo user; route/stop list, khách/địa chỉ/cam kết/ETA/ghi chú, gọi và mở chỉ đường qua tọa độ.
- Persist command trước khi báo lưu; client_action_id giữ nguyên qua retry/restart; giữ thứ tự từng chuỗi phụ thuộc. DEC-036: 409 → CONFLICT, chỉ tạm dừng cùng delivery/stop hoặc stop phụ thuộc START_TRIP; các entity độc lập tiếp tục sync. Xem dữ liệu mới, xác nhận bỏ có lý do/audit; giữ DISCARDED và payload cũ, command mới dùng ID mới và liên kết command cũ. Không tự retry conflict hoặc mutate payload; quyết định bỏ offline được lưu và sync idempotently.
- Server lưu receipt theo actor/client_action_id cùng transaction nghiệp vụ, ít nhất 24 giờ; cùng id khác payload bị từ chối; replay không tạo event/audit trùng. Áp dụng state machine, quyền, POD gate hiện có khi nhận command, không tin cache.
- Geofence server dựa GPS xe từ Traccar, bán kính 50m, không dùng GPS điện thoại thay nguồn thiết bị; chỉ GPS hợp lệ/fresh. Không đổi quy tắc GPS freshness.
- Sửa ARRIVED theo DEC-034: chỉ ARRIVED → EN_ROUTE, trip ACTIVE, lý do/audit đầy đủ; khóa auto-ARRIVED sau sửa, GPS hợp lệ >70m mới re-arm, lần vào ≤50m tiếp theo mới ARRIVED; không timeout re-arm. Command tham chiếu event ARRIVED đang sửa để không đảo một lần đến mới bằng dữ liệu cache cũ.
- Không triển khai camera/upload POD M5, tracking M6, chi phí M7. Giao thành công vẫn bị chặn khi chưa có POD hợp lệ. Tài xế chỉ đề xuất giao lại theo DEC-011.
- DEC-035 chấp nhận tạm thời hai advisory braces/node-forge cho M4 development/local/CI, không production; giữ toàn bộ kiểm soát và audit/runtime gates, review muộn nhất 02/11/2026 hoặc trước production. Không sửa DEC-033 và các DEC cũ.

Kiểm tra: SQLite thực cho queue/restart/order/retry/concurrency, PostGIS thật cho idempotency/RBAC/geofence/audit và migration; lint/typecheck/build/export, Docker/health và CI remote khi chốt source. Không tự chuyển M5.
