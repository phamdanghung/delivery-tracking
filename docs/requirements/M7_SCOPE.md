# M7 — Fuel / Expenses / Maintenance / Safety

Base M6 merge `b1e30f1cb3f446f38730261c39e3d8961bf4271a`, branch `codex/m7-fuel-maintenance-alerts`. Reuse canonical `fleet-delivery-dev`; head khi bắt đầu 0008, M7 nâng lên 0009. Giữ legacy, migrations 0001–0008 và contract M1–M6.

## Đã khóa

- FUEL-01/02/03/04, ASSET-02/03, SAFE-01/03; SAFE-02 chỉ khi thiết bị/nguồn đáng tin cậy. Truy vết theo Technical Pack 08/10, WEB-10/11/12 và DRV-07/08.
- DEC-006: chênh lệch tuyệt đối >15%, không cảnh báo ở đúng 15%; công thức distance_km × driving_l_per_100km /100 + idle_hours × idling_l_per_hour.
- DEC-007: ngoài giờ local 18:00 inclusive đến 07:30 exclusive; xe nổ máy hoặc di chuyển, có ngoại lệ được duyệt.
- DEC-008: bảo dưỡng cấu hình riêng theo xe; ASSET-03 giấy tờ/nhắc hết hạn thuộc M7 theo Pack/WEB-11.
- DEC-018: NEW → SEEN → RESOLVED tách biệt; thay schema/contract additive ở M7.
- DEC-020/036: giữ offline/idempotency và conflict theo entity; không mutate/replay command cũ hoặc khóa queue không liên quan.
- DEC-021: không remote immobilization. Không triển khai reports/hardening/deployment M8.
- DEC-046 chỉ áp dụng M6, không tự mở rộng accepted risk cho M7.

## Quyết định bổ sung đã chốt

1. DEC-047: kỳ FROM/TO có timezone do ADMIN/DISPATCHER xác nhận; nhiều entries, telemetry tính một lần; chia profile theo hiệu lực; signed variance, ABS >15%; thiếu dữ liệu không giả variance; version/audit tính lại, FINAL không overlap.
2. DEC-048: ADMIN cấu hình safety/ngoại lệ hữu hạn; GPS/ACC/activity tin cậy, incidents chống trùng REST/socket; NEW → SEEN → RESOLVED với lý do/audit. Không tự triển khai harsh braking/out-of-area khi chưa có threshold/contract phê duyệt.
3. DEC-049: additive contracts được phép; ADMIN quản trị, DISPATCHER ghi/xem fuel/expenses và xem maintenance; DRIVER chỉ own expenses offline M4, receipt private tùy chọn. Maintenance theo km/ngày/đến trước, event hoặc mốc ADMIN có nguồn; lead cấu hình tường minh, không mặc định tự đoán.

Ba nhóm đã được chủ dự án chốt ngày 14/10/2026, cho phép tiếp tục API/migration/UI tương ứng. Các DEC accepted-risk cũ không áp dụng M7.

## Thiết kế triển khai theo quyết định đã chốt

- Migration `0009` additive, không sửa 0001–0008. Profiles DATE có hiệu lực theo ngày công ty Asia/Bangkok, khoảng `[effective_from,effective_to)`; period và entries dùng `[from_at,to_at)` để các kỳ liền nhau không double-count. Exclusion constraints bảo vệ profile overlap và FINAL overlap cả khi concurrent.
- Mỗi lần tính/chốt/tính lại ghi version bất biến, applied profiles/entries/telemetry, actor/time/reason. GPS history sử dụng tiêu chuẩn gap 120s đã có ở M1; không nối qua LOST hoặc tự ngoại suy idle ở biên. Km lấy report Traccar và kiểm tra coverage khớp positions. Thiếu dữ liệu không tạo variance/alert.
- Tính nhiên liệu/variance bằng phân số chính xác từ km, seconds idle, rates; chỉ chuyển decimal khi biểu diễn. Giữ nguyên công thức và ABS >15, tránh cảnh báo giả tại đúng ±15 khi chia thời gian thành profile segments.
- Fuel entries và maintenance events dùng `client_action_id` khi tạo; receipts private/versioned và bind đúng actor/vehicle/kind hoặc actor/trip/expense command. Ảnh optional, reuse image validation/EXIF/storage helpers M5; không mở POD/customer tracking.
- Maintenance theo rule riêng từng xe, lead do ADMIN nhập; latest event hoặc baseline có nguồn rõ. Odometer thực Traccar khi có; không suy km từ tuyến. History append-only, mutation cấu hình/giấy tờ có lý do/audit.
- Safety xử lý trong ingest GPS chung REST/socket; incident lifecycle độc lập NEW/SEEN/RESOLVED. Resolve không làm incident đang tiếp tục sinh alert mỗi ping. Không guessed speeding threshold/harsh braking/out-of-area; không remote immobilization.
- WEB-10/11/12 reuse shell/tokens; DRV-07 dùng tab Chi phí hiện có, DRV-08 reuse outbox/conflict M4. Expense action theo trip entity, không khóa queue không liên quan; actor-scoped cache và credential publication bảo vệ việc đổi tài khoản.

Xác minh targeted trước; full regression/migration round-trip/build/exports/canonical Docker/remote CI khi chốt theo CODEX_TOKEN_RULES. Kết quả cuối ghi trong M7_FINAL.md; audit nguyên trạng, không tự mở rộng DEC-046 cho M7. Không tự merge hoặc chuyển M8.
