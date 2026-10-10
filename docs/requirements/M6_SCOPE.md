# M6 — Customer tracking

Branch `codex/m6-customer-tracking-eta`, base M5 merge `a6438c903b4eae278a4bc99be3de89d71d19b5fd`.

Áp dụng NOTIF-01/ETA, DEC-005/009/015/016/022/041, AT-10/11, UX CUS-01/02/03 và WEB-08. Giữ modular monolith FastAPI, Next.js public route `/t/{trackingToken}`, Traccar GPS, OSRM self-host và Redis; reuse canonical **fleet-delivery-dev**. Legacy fleet-delivery giữ PRESERVED; không migrate/reset/prune/xóa dữ liệu legacy hoặc downgrade canonical.

- Token random ≥128 bit, chỉ lưu hash trong DB, public rate limit. Khách chỉ đọc đúng delivery của token, không dùng token làm auth cho API nội bộ hoặc POD.
- Chỉ trả DTO public tối thiểu: trạng thái/mã đơn, GPS được phép, cập nhật/freshness và ETA. Không xe/đơn/khách khác, route đầy đủ, GPS history, notes/phone/actor/internal IDs/POD hoặc credentials nội bộ.
- Link hết hiệu lực DELIVERED +1 giờ; 410 cho hết hiệu lực/thu hồi. Nhân viên tạo/copy link gửi Zalo thủ công, không SMS/ZNS tự động.
- Giao diện mobile-first theo CUS-01/02/03, loading/empty/error/GPS stale/expired, không render GPS khi link không hợp lệ. Private headers/no-store/no-referrer/noindex và không log raw token.
- ETA phải cập nhật từ dữ liệu thật, không giả tọa độ, không tự geocode hoặc gửi địa chỉ khách ra provider ngoài. Không thay optimization/state machine M3–M5.

## Quyết định đã chốt

Áp dụng DEC-042/043/044/045: token theo lượt giao, cấp/thu hồi từng link, privacy sau giao và ETA từ GPS fresh + OSRM + tuyến đã duyệt. Không bổ sung endpoint quản lý ngoài create/revoke đã được duyệt.

DEC-040 accepted risk chỉ cho M5, chưa mở rộng M6. Không tự chấp nhận advisory M6; audit/runtime gates vẫn bắt buộc khi chốt. Không chuyển M7.

## Contract và triển khai

- `POST /api/v1/tracking-links`: `{delivery_id}` → 201 `{id,url,expires_at:null}`; chỉ ADMIN/DISPATCHER, lượt ACTIVE ở EN_ROUTE/ARRIVED/DELIVERING. URL chứa token random 256 bit, chỉ trả lần tạo.
- `POST /api/v1/tracking-links/{identifier}/revoke`: ADMIN/DISPATCHER; idempotent, audit một lần, không thu hồi link khác.
- `GET /api/v1/public/tracking/{token}`: anonymous; 200 DTO tối thiểu `code/status/completed_at/expires_at/gps/eta_at/eta_status`, 410 chung cho không hợp lệ/hết hạn/thu hồi. Không có query để chuyển delivery hoặc vehicle.
- GPS chỉ đọc snapshot xe gắn đúng lượt; NORMAL ≤30s, STALE ≤120s, LOST >120s theo DEC-015. Snapshot cũ chỉ hiển thị vị trí ghi nhận gần nhất, không dùng tính ETA. Missing/future/invalid không tạo vị trí giả.
- Nếu dữ liệu có nhiều chuyến ACTIVE cho cùng xe, không xác định chắc chuyến đang phục vụ: giữ thông tin đơn nhưng ẩn GPS/ETA. Đây là privacy guard; không thay quy tắc lập/bắt đầu chuyến M2.
- ETA cộng thời gian đường thực từ GPS qua các điểm chưa hoàn tất đến điểm khách, thời gian chờ cửa sổ hẹn và service time của các điểm trước đó trong snapshot tuyến đã duyệt; không trả điểm/geometry nội bộ. Cache ETA 10s theo plan/GPS/trạng thái các điểm; mỗi request vẫn kiểm tra token/lifecycle trước khi dùng cache. OSRM/GPS không hợp lệ trả UNKNOWN.
- Redis rate limit peer + token, fail closed nếu Redis lỗi. Không tin header IP do client tự gửi. Anonymous BFF không chuyển cookie/Authorization nội bộ. Header no-store/no-referrer/noindex cả trang và API.
- Migration additive `0008`, không đổi migration 0001–0007. Link legacy thiếu attempt binding giữ nguyên dữ liệu nhưng không hợp lệ; không tự gán lượt đoán.
- UI tạo/copy nhiều link và thu hồi từng link vừa tạo hoặc theo ID đã lưu, không endpoint lấy lại plaintext. Route public `/t/{trackingToken}` không có navigation nội bộ.

Theo DEC-045, trước mỗi ETA/cache phải đối chiếu toàn bộ stop/sequence và tọa độ/thời gian hẹn hiện hành với snapshot đã duyệt. Sai khác trả UNKNOWN; xác minh OSRM thật kể cả cache còn hạn. DELIVERED không truy vấn GPS hay tính ETA. Không đổi API/state machine.
