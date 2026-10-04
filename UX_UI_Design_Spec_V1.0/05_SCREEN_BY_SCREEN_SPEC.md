# 05 - SCREEN-BY-SCREEN SPEC

## A. WEB QUẢN TRỊ / ĐIỀU PHỐI

### WEB-01 - Đăng nhập
**Mục tiêu:** vào hệ thống nhanh, rõ lỗi.

Thành phần:
- Logo/tên hệ thống.
- Email/tên đăng nhập.
- Mật khẩu + show/hide.
- Đăng nhập.
- Thông báo lỗi không tiết lộ quá mức.

### WEB-02 - Tổng quan hôm nay
**Mục tiêu:** trong 5-10 giây biết tình hình vận hành.

KPI bắt buộc:
- Tổng đơn hôm nay.
- Đã giao.
- Đang giao.
- Giao thất bại/hẹn lại.
- Nguy cơ trễ.

Khối chính:
- Bản đồ xe live.
- Cần xử lý ngay.
- Tiến độ chuyến hôm nay.
- Cảnh báo GPS/offline/ngoài giờ.

Không biến dashboard thành nơi chứa mọi báo cáo lịch sử.

### WEB-03 - Bản đồ xe trực tiếp
- Bản đồ full-workspace.
- Panel trái: danh sách xe, tìm kiếm, filter trạng thái.
- Popup xe: biển số, tài xế, tốc độ, ACC, GPS last seen, điểm hiện tại.
- Nếu GPS cũ: marker vẫn ở vị trí cuối nhưng phải ghi rõ **Vị trí cuối ghi nhận**.

### WEB-04 - Danh sách đơn giao
Cột mặc định:
- Mã đơn.
- Khách/người nhận.
- Địa chỉ rút gọn.
- Cam kết thời gian.
- Chuyến/xe.
- ETA hoặc kết quả giao.
- Trạng thái.

Filter:
- ngày;
- trạng thái;
- đúng giờ/trễ;
- xe/tài xế;
- tìm theo khách/SĐT/mã.

Bulk action: tạo chuyến từ các đơn đã chọn.

### WEB-05 - Tạo/Sửa đơn
Hai vùng:
1. **Nháp Zalo**.
2. **Form chuẩn**.

Nút `Tách thông tin` chỉ điền gợi ý, không auto-save.

Field tối thiểu:
- khách/người nhận;
- SĐT;
- địa chỉ;
- loại thời gian hẹn;
- mốc/khung giờ;
- khối lượng;
- thể tích;
- ghi chú.

Validation hiển thị tại field.

### WEB-06 - Lập chuyến
- Chọn ngày.
- Danh sách đơn chưa phân.
- Chọn xe/tài xế.
- Điểm đầu/cuối mặc định công ty, cho phép đổi.
- Tổng kg/m3 so với xe.
- Cảnh báo quá tải không khóa nút tiếp tục.
- CTA: **Tối ưu tuyến**.

### WEB-07 - Duyệt tuyến tối ưu
Bố cục desktop 65/35: bản đồ / panel tuyến.

Phải hiển thị:
- thứ tự điểm;
- loại cam kết;
- ETA;
- đúng giờ/nguy cơ trễ/trễ;
- quãng đường;
- tổng thời gian;
- lý do cảnh báo nếu không thể đáp ứng tất cả.

Nếu cho kéo thả thứ tự thủ công, sau thay đổi phải tính lại ETA/cảnh báo trước khi duyệt.

### WEB-08 - Chi tiết đơn
Header:
- mã đơn + trạng thái + hành động hợp lệ.

Tab/section:
- Thông tin giao.
- Timeline trạng thái.
- Ảnh POD.
- Tracking link (copy).
- Lịch giao lại.
- Nhật ký thay đổi quan trọng.

### WEB-09 - Lịch sử hành trình xe
- Chọn xe + ngày/khung giờ.
- Bản đồ playback.
- Danh sách điểm dừng + thời gian dừng.
- Chỉ báo đoạn thiếu dữ liệu GPS.

### WEB-10 - Nhiên liệu & chi phí
Hai tab:
- Nhiên liệu: dự kiến, thực tế, % chênh, cảnh báo >15%.
- Chi phí: cầu đường, bãi xe, bốc xếp, khác.

### WEB-11 - Bảo dưỡng & giấy tờ
- Card từng xe.
- Hạng mục bảo dưỡng cấu hình riêng.
- Km hiện tại, km đến hạn.
- Đăng kiểm/bảo hiểm: ngày hết hạn + countdown.

### WEB-12 - Cảnh báo an toàn
Danh sách theo thời gian:
- ngoài giờ 18:00-07:30;
- quá tốc độ nếu có dữ liệu;
- ra ngoài vùng;
- phanh/tăng tốc gấp nếu thiết bị hỗ trợ.

Mỗi cảnh báo có trạng thái: Mới / Đã xem / Đã xử lý.

### WEB-13 - Báo cáo
Giai đoạn đầu ưu tiên bảng + KPI, không cần dashboard BI phức tạp.
- đúng giờ;
- hiệu quả xe;
- km;
- nhiên liệu;
- giao thất bại;
- chi phí.

### WEB-14 - Người dùng & phân quyền
- Danh sách user.
- Vai trò.
- trạng thái hoạt động.
- Không hiển thị quyền dưới dạng ma trận 100 checkbox nếu chưa cần; ưu tiên role preset + quyền bổ sung.

---

## B. APP TÀI XẾ

### DRV-01 - Đăng nhập
Đơn giản, không chứa thông tin quản trị.

### DRV-02 - Chuyến hôm nay
Ưu tiên card **Điểm tiếp theo**.

Phải thấy ngay:
- tên khách;
- cam kết;
- ETA;
- đúng/trễ;
- khoảng cách;
- nút mở chỉ đường.

Danh sách bên dưới dùng timeline theo thứ tự.

### DRV-03 - Chi tiết điểm
- khách, SĐT + nút gọi;
- địa chỉ;
- giờ/khung giờ;
- ETA;
- ghi chú;
- mở Google/Apple Maps;
- CTA theo trạng thái hợp lệ.

### DRV-04 - Thao tác trạng thái
Không cho tài xế thấy dropdown toàn bộ state machine.
Chỉ hiển thị hành động hợp lệ theo trạng thái hiện tại, ví dụ:
- Bắt đầu bàn giao.
- Giao thành công.
- Giao không thành công.
- Sửa "Đã đến" khi cần.

### DRV-05 - Chụp POD
- Camera/album theo permission.
- Preview ảnh.
- ít nhất 1 ảnh mới được enable `Giao thành công`.
- Hiển thị GPS/time capture ở metadata; không cần đóng quá nhiều text lên ảnh nếu backend lưu metadata riêng, trừ khi nghiệp vụ yêu cầu watermark.

### DRV-06 - Giao thất bại
- Lý do bắt buộc.
- Ghi chú tùy chọn.
- Hẹn giao lại: ngày + kiểu cam kết thời gian mới.
- Xác nhận rõ tác động.

### DRV-07 - Chi phí
Form cực ngắn:
- loại chi phí;
- số tiền;
- ghi chú;
- ảnh biên lai tùy chọn/theo nghiệp vụ.

### DRV-08 - Trạng thái đồng bộ
Không cần màn hình kỹ thuật phức tạp.
Hiển thị:
- đã đồng bộ;
- chờ đồng bộ;
- lỗi;
- thử lại.

---

## C. TRACKING KHÁCH

### CUS-01 - Link đang hoạt động
- Tên/mã đơn tối thiểu.
- Trạng thái.
- ETA nổi bật nhất.
- Bản đồ với vị trí xe chính xác.
- Thời điểm GPS cập nhật gần nhất.
- Không hiển thị tuyến đầy đủ hoặc khách khác.

### CUS-02 - Đã giao nhưng link còn hiệu lực
Trong 1 giờ sau `DELIVERED`:
- trạng thái **Đã giao thành công**;
- không cần tiếp tục làm nổi vị trí live nếu xe đã rời khách; ưu tiên thông báo đơn đã hoàn tất;
- link tự hết hạn theo backend.

### CUS-03 - Link hết hạn/không hợp lệ
Thông báo đơn giản:
- "Liên kết theo dõi đã hết hiệu lực" hoặc "Liên kết không hợp lệ".
- Không rò rỉ lý do kỹ thuật/token.
- Không hiển thị GPS.
