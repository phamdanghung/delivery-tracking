# 06 - UI/UX ACCEPTANCE TESTS

## 1. Nguyên tắc nghiệm thu
Frontend không chỉ "đúng dữ liệu" mà phải đúng luồng, trạng thái và khả năng sử dụng.

## 2. Web
### UX-WEB-01 Dashboard
Given có chuyến đang chạy và 1 đơn nguy cơ trễ,
When mở Dashboard,
Then người dùng thấy cảnh báo nguy cơ trễ trong màn hình đầu, không cần vào báo cáo.

### UX-WEB-02 GPS cũ
Given vị trí xe không cập nhật theo ngưỡng stale,
When mở live map,
Then giao diện ghi rõ đây là vị trí cuối ghi nhận và thời điểm last seen; không hiển thị như live bình thường.

### UX-WEB-03 Tạo đơn từ Zalo
Given người dùng dán nội dung Zalo,
When bấm Tách thông tin,
Then hệ thống chỉ điền gợi ý vào form và người dùng vẫn có thể sửa trước khi lưu.

### UX-WEB-04 Ba kiểu hẹn
Form tạo đơn phải hỗ trợ:
- giờ cố định;
- khung giờ;
- trước một mốc.
Field thời gian thay đổi phù hợp theo lựa chọn.

### UX-WEB-05 Quá tải
Given chuyến vượt tải,
Then hiển thị warning rõ nhưng CTA tạo/duyệt chuyến vẫn khả dụng nếu quyền cho phép.

### UX-WEB-06 Duyệt tuyến
Trước khi duyệt phải thấy ít nhất: thứ tự, ETA, trạng thái đúng/trễ, tổng km, tổng thời gian.

### UX-WEB-07 Sửa ARRIVED
Khi sửa "Đã đến", UI bắt buộc nhập lý do trước khi xác nhận.

## 3. App tài xế
### UX-DRV-01 Tác vụ chính
Từ màn hình chuyến hôm nay đến mở chỉ đường cho điểm tiếp theo không quá 2 thao tác chính.

### UX-DRV-02 POD bắt buộc
Không enable `Giao thành công` nếu chưa có ít nhất 1 ảnh POD hợp lệ.

### UX-DRV-03 Offline
Khi mất mạng:
- app có banner rõ;
- vẫn xem được chuyến đã tải;
- thao tác giao được lưu;
- không hiện lỗi chung khiến tài xế tưởng dữ liệu đã mất.

### UX-DRV-04 Đồng bộ lại
Khi mạng trở lại, UI phản ánh tiến trình đồng bộ; thao tác trùng không tạo bản ghi giao trùng.

### UX-DRV-05 Nút chạm
Các nút tác vụ chính đạt target tối thiểu 44x44px; CTA chính ưu tiên >=48px chiều cao.

## 4. Tracking khách
### UX-CUS-01 Data isolation
Khách chỉ thấy dữ liệu một delivery.

### UX-CUS-02 Vị trí chính xác
Khi link hợp lệ và đơn đang giao, bản đồ hiển thị vị trí GPS chính xác + thời điểm cập nhật.

### UX-CUS-03 Hết hạn
Sau 1 giờ từ `DELIVERED`, UI chỉ hiển thị link hết hiệu lực và không render vị trí xe.

## 5. Design system
### UX-DS-01 Status
Không trạng thái quan trọng nào chỉ phân biệt bằng màu; phải có text/icon.

### UX-DS-02 Loading
Màn hình dữ liệu có loading state; không để trang trắng.

### UX-DS-03 Empty
Danh sách rỗng có mô tả và CTA hợp lý nếu có hành động tiếp theo.

### UX-DS-04 Error
Lỗi mạng/API có nội dung dễ hiểu + Retry khi có thể.

### UX-DS-05 Accessibility
Văn bản thông thường hướng tới contrast >= 4.5:1, focus web rõ và icon tương tác có accessible label.

## 6. Kiểm tra responsive
- Web: 1366x768 và 1440x900 là baseline.
- Tablet: không được vỡ layout ở 768px; các bảng có horizontal scroll hợp lý.
- Driver app: baseline 360-430px width.
- Tracking: mobile-first 360-430px, desktop vẫn đọc được.

## 7. Điều kiện đạt
Một màn hình chỉ được coi là hoàn tất khi:
- đúng dữ liệu;
- đúng quyền;
- đúng trạng thái;
- có loading/empty/error;
- responsive;
- không có tác vụ nghiệp vụ ẩn sau thao tác khó hiểu;
- pass acceptance test tương ứng.
