# M4 — Driver App / offline / geofence

Branch `codex/m4-driver-offline-geofence`, base M3 merge `8d95b1c7c08df79f24335526c9e2763a02309e29`.

Áp dụng ROUT-03/04, DEC-004/014/015/020/028, AT-05/06 và UX DRV-01/02/03/04/06/08. React Native/Expo SDK 57 hiện tại, Expo Router theo AGENTS.md; SQLite cache/outbox, SecureStore cho token, API/RBAC và GPS Traccar hiện có. Không đổi baseline M1/M2/M3 contracts; bổ sung contract M4 có phiên bản cho sync/cache cần thiết.

- Cache dữ liệu chuyến đã duyệt của chính tài xế theo user; route/stop list, khách/địa chỉ/cam kết/ETA/ghi chú, gọi và mở chỉ đường qua tọa độ.
- Persist command trước khi báo lưu; client_action_id giữ nguyên qua retry/restart; queue tuần tự, không bỏ qua action lỗi; sync khi reconnect/foreground, trạng thái rõ và thử lại.
- Server lưu receipt theo actor/client_action_id cùng transaction nghiệp vụ, ít nhất 24 giờ; cùng id khác payload bị từ chối; replay không tạo event/audit trùng. Áp dụng state machine, quyền, POD gate hiện có khi nhận command, không tin cache.
- Geofence server dựa GPS xe từ Traccar, bán kính 50m, không dùng GPS điện thoại thay nguồn thiết bị; chỉ GPS hợp lệ/fresh. Không đổi quy tắc GPS freshness.
- Sửa ARRIVED theo DEC-034: chỉ ARRIVED → EN_ROUTE, trip ACTIVE, lý do/audit đầy đủ; khóa auto-ARRIVED sau sửa, GPS hợp lệ >70m mới re-arm, lần vào ≤50m tiếp theo mới ARRIVED; không timeout re-arm. Command tham chiếu event ARRIVED đang sửa để không đảo một lần đến mới bằng dữ liệu cache cũ.
- Không triển khai camera/upload POD M5, tracking M6, chi phí M7. Giao thành công vẫn bị chặn khi chưa có POD hợp lệ. Tài xế chỉ đề xuất giao lại theo DEC-011.
- DEC-033 chỉ chấp nhận security M3; không tự mở rộng sang M4. Audit/runtime gates tiếp tục hiển thị.

Kiểm tra: SQLite thực cho queue/restart/order/retry/concurrency, PostGIS thật cho idempotency/RBAC/geofence/audit và migration; lint/typecheck/build/export, Docker/health và CI remote khi chốt source. Không tự chuyển M5.
