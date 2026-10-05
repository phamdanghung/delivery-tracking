# M2 — phạm vi và các điểm cần chốt trước triển khai

Ngày rà soát: 05/10/2026. Trạng thái: triển khai theo DEC-025–028 đã được chủ dự án chốt. M1 đã PASS WITH ACCEPTED RISK theo DEC-024, không làm lại M1.

## Phạm vi đã có căn cứ

ROUT-01, ROUT-05, POD-03, ASSET-01: nhập/sửa đơn trước khi lập chuyến; nháp Zalo chỉ gợi ý, không tự lưu; ba kiểu hẹn; danh sách/chi tiết/timeline; trips/stops và phân xe/tài xế; state machine; lý do thất bại; tài xế đề xuất giao lại và điều phối xác nhận theo DEC-010/011; tải trọng chỉ cảnh báo. WEB-04/05/06/08 theo UX/UI, tái sử dụng auth/BFF/sidebar/topbar/design tokens hiện có.

Giữ FastAPI modular monolith, Next.js, PostgreSQL/PostGIS và baseline 0001/0002. Không optimization/ETA provider M3, app/offline/geofence M4, upload POD M5 hoặc customer tracking M6. DELIVERED vẫn phải kiểm tra ảnh POD hợp lệ, không mở bypass để hoàn tất ở M2. Chưa tạo quyết định mới thay chủ dự án.

## Quyết định đã chốt cho các điểm cần làm rõ

| Điểm | Quyết định đã duyệt | Triển khai M2 |
|---|---|---|
| Duyệt/phân chuyến trước M3 | DEC-025 (D1) | Chỉ lưu DRAFT; không duyệt/xuất hoặc giả ETA. |
| Điểm đầu/cuối mặc định | DEC-026 (E2), DEC-002 | ENV/config; báo thiếu cấu hình, yêu cầu tọa độ hợp lệ trước lưu. |
| Quyền hủy đơn | DEC-027 | ADMIN/DISPATCHER, CREATED/PLANNED/ASSIGNED, lý do và audit; DRIVER bị chặn. |
| Sửa ARRIVED nhận sai | DEC-028, DEC-004 | Để M4; không transition ngược đặc biệt trong M2. |

DEC-025: web chỉ lưu chuyến DRAFT với xe/tài xế/stops; duyệt/xuất sau M3. Không có API duyệt mới để bypass giới hạn này. DEC-026: COMPANY_LATITUDE/COMPANY_LONGITUDE từ ENV/config; thiếu cấu hình thì báo rõ, chỉ lưu khi điểm đầu/cuối đã có tọa độ hợp lệ (điều phối được nhập điểm thay thế theo DEC-002). DEC-027: ADMIN/DISPATCHER hủy CREATED/PLANNED/ASSIGNED, lý do và audit bắt buộc; DRIVER bị chặn. DEC-028: sửa ARRIVED đặc biệt để M4; không transition ngược ở M2.

## Contract/schema bổ sung không breaking

- Giữ endpoint V1.0 `/deliveries`, `/deliveries/{id}/status`, `/deliveries/{id}/reschedule`, `/trips`, `/trips/{id}/start`; bổ sung schemas và endpoint đọc/sửa/detail cần WEB-04/05/08 vào `openapi/m2.openapi.json`, không sửa baseline OpenAPI.
- Delivery dùng `commitment_type` theo SQL: FIXED_TIME/appointment_at, TIME_WINDOW/window_start/window_end, BEFORE_DEADLINE/deadline_at; timestamps có timezone, phone/address bắt buộc, weight/volume không âm; tọa độ explicit, không triển khai geocoding M3.
- Trip giữ liên kết vehicle/driver theo từng chuyến, stops có thứ tự. Vehicle/user/profile không hoạt động không được phân công; quá tải chỉ warning. Không tự đặt giới hạn một chuyến/ngày vì chưa có contract khung giờ chuyến.
- DEC-011 cần lưu đề xuất lịch giao lại riêng, không thay lịch/status chính khi DRIVER đề xuất. Bảng `delivery_reschedule_proposals` lưu actor, cam kết mới, thời gian tạo và xác nhận; chỉ operator xác nhận mới tạo RESCHEDULED và audit/event. Không tự thêm workflow từ chối chưa đặc tả.
- SQL thiếu TripStop.status so với file 02: migration mới bổ sung status theo delivery_status để lịch sử lần giao không bị đổi theo đơn đã hẹn lại. Baseline giữ nguyên. Backfill từ trạng thái delivery cho các stops cũ vì baseline chưa lưu lịch sử status riêng.

Các đơn chọn vào chuyến nháp chuyển CREATED/RESCHEDULED → PLANNED theo định nghĩa ngày/chuyến đã khóa; ASSIGNED chỉ sau duyệt ở M3. Không trả ETA/km/đúng-trễ giả; bộ lọc đúng/trễ ghi chưa có dữ liệu ETA ở M2. API start/status hỗ trợ chuyến PLANNED/ACTIVE hợp lệ đã được duyệt từ milestone sau hoặc fixture test riêng; không cho start DRAFT. POD DELIVERED gate kiểm tra ảnh đã upload vào storage private thực tế; không triển khai upload M5.

## Kiểm tra nghiệm thu

Test liên quan theo từng phần; khi chốt M2 chạy full regression và build phần source thay đổi, real database migration upgrade/downgrade/upgrade trên DB riêng, AT-03/09/12, RBAC/state invalid/concurrency/audit, UI loading/empty/error/permission/reschedule, Docker/health và CI remote thực tế. Bằng chứng M1 còn hợp lệ không chạy lại chỉ vì bắt đầu lượt mới. Tạo branch/PR M2 và M2_FINAL khi triển khai xong; không chuyển M3.

## Security gate

DEC-024 chỉ chấp nhận braces/node-forge cho M1 development/local/CI, không tự mở rộng sang M2. Trước kết luận M2 cần kiểm tra advisory/runtime surface của source M2 và xin quyết định riêng nếu vẫn phải dùng exception. Không suppress, force fix, downgrade Expo/RN hoặc bỏ audit/gates.
