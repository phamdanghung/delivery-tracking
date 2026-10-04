# 04 - DESIGN SYSTEM

## 1. Tinh thần
- Hiện đại, chuyên nghiệp, vận hành nhanh.
- Nền sáng, mật độ thông tin vừa phải.
- Bản đồ và trạng thái là trung tâm.
- Tránh hiệu ứng trang trí không phục vụ quyết định.

## 2. Màu cơ bản
> Đây là token đề xuất cho Giai đoạn 1; có thể thay accent theo nhận diện thương hiệu mà không đổi ý nghĩa trạng thái.

- `primary-600`: **#0F6CBD** - hành động chính, link.
- `primary-50`: **#EFF6FF** - nền nhấn nhẹ.
- `neutral-950`: **#111827** - chữ chính.
- `neutral-600`: **#4B5563** - chữ phụ.
- `neutral-300`: **#D1D5DB** - border.
- `neutral-100`: **#F3F4F6** - nền phụ.
- `success-600`: **#15803D** - đúng giờ/đã giao.
- `warning-600`: **#B45309** - nguy cơ trễ/cảnh báo tải.
- `danger-600`: **#B91C1C** - trễ/lỗi/giao thất bại.
- `info-600`: **#0369A1** - thông tin hệ thống.

Không dùng màu đơn độc để truyền nghĩa: luôn có icon/chữ/badge.

## 3. Typography
### Web
- Font: Inter hoặc font hệ thống tương đương.
- Page title: 24/32, semibold.
- Section title: 18/28, semibold.
- Body: 14-16/22-24.
- Table: 14/20.

### Mobile
- Page title: 22/28, semibold.
- Card title: 17/24, semibold.
- Body: tối thiểu 16/22 cho nội dung chính.
- Caption: 13-14 nhưng không dùng cho thông tin quan trọng.

## 4. Spacing
Dùng thang 4px: `4, 8, 12, 16, 24, 32, 40, 48`.
- Card padding web: 16-24.
- Card padding mobile: 16.
- Khoảng giữa section: 24-32.

## 5. Radius & shadow
- Radius input/button: 8px.
- Card: 12px.
- Modal: 16px.
- Shadow nhẹ; không dùng shadow dày cho mọi card.

## 6. Nút
### Primary
Một hành động chính/màn hình: Lưu đơn, Duyệt chuyến, Giao thành công.

### Secondary
Hành động hỗ trợ: Tối ưu lại, Chụp thêm.

### Destructive
Giao thất bại, Hủy đơn phải có kiểu danger và xác nhận phù hợp.

### Quy tắc mobile
- Chiều cao nút tối thiểu 48px.
- Target chạm tối thiểu 44x44px.
- Hành động chính nên full-width ở cuối màn hình khi phù hợp.

## 7. Form
- Label luôn hiển thị, không dùng placeholder thay label.
- Trường bắt buộc có `*` + lỗi cụ thể.
- Kiểm tra địa chỉ nên hiển thị tọa độ/bản đồ nhỏ khi cần.
- Kiểu hẹn dùng segmented/radio rõ ràng.
- Không xóa dữ liệu người dùng sau lỗi submit.

## 8. Table Web
- Header sticky nếu bảng dài.
- Hỗ trợ lọc nhanh.
- Trạng thái dùng badge.
- Cột hành động không nhồi quá 3 icon; tác vụ phụ vào menu `...`.
- Row click mở chi tiết; checkbox riêng cho bulk action.

## 9. Badge trạng thái
- Mới tạo: neutral.
- Đã lên kế hoạch/đã phân: info.
- Đang đi/đã đến/đang bàn giao: primary/info.
- Giao thành công: success.
- Giao thất bại/trễ: danger.
- Hẹn giao lại: warning.
- Đã hủy: neutral/danger subtle.

## 10. Bản đồ
- Marker xe khác marker điểm giao.
- Xe đang được chọn có halo/outline.
- Không hiển thị quá nhiều label cùng lúc.
- Popup xe: biển số, tốc độ, ACC, GPS cập nhật lúc nào, điểm đang phục vụ.
- Popup điểm: thứ tự, khách, cam kết, ETA, trạng thái đúng/trễ.

## 11. Trạng thái GPS
- `< 30 giây`: Bình thường.
- Dữ liệu cũ hơn ngưỡng cấu hình: hiển thị **GPS cập nhật chậm**.
- Mất tín hiệu: badge rõ + thời điểm dữ liệu cuối; không giả vờ marker là live.

## 12. Offline app
Banner cố định ở đầu:
- Offline: "Đang ngoại tuyến - thao tác sẽ được lưu trên máy".
- Đồng bộ: "Đang đồng bộ 3 thao tác...".
- Lỗi: "2 thao tác chưa đồng bộ" + nút xem/Thử lại.

## 13. Accessibility
- Contrast văn bản thường mục tiêu WCAG AA 4.5:1.
- Focus state rõ trên web.
- Không dùng hover làm cách duy nhất để thấy hành động.
- Icon có label/aria-label.
- Status không dựa chỉ vào đỏ/xanh.
