# 05 - TRẠNG THÁI VÀ QUY TẮC

## 1. State machine đơn giao
`CREATED -> PLANNED -> ASSIGNED -> EN_ROUTE -> ARRIVED -> DELIVERING -> DELIVERED`

Nhánh lỗi:
- `ARRIVED|DELIVERING -> FAILED`
- `FAILED -> RESCHEDULED -> PLANNED`
- `CREATED|PLANNED|ASSIGNED -> CANCELLED` (theo quyền)

## 2. Quy tắc ARRIVED
- Geofence bán kính 50 m.
- Khi vị trí xe đi vào geofence của điểm đang phục vụ, server tạo event `ARRIVED` tự động.
- Tài xế và Điều phối được sửa nếu nhận sai; bắt buộc lý do và audit trước/sau.

## 3. Quy tắc giao thành công
- Phải có ít nhất 1 `PodPhoto` đã lưu cục bộ/đồng bộ hợp lệ.
- Không bắt buộc chữ ký.
- Nếu offline, app ghi thao tác vào queue với `sync_id`; server xử lý idempotent.

## 4. Giao thất bại và giao lại
- `FAILED` bắt buộc `failure_reason`.
- `RESCHEDULED` bắt buộc thời gian cam kết mới.

## 5. Cam kết thời gian
- FIXED_TIME: ưu tiên đạt gần mốc đã hẹn; ngưỡng đúng giờ cấu hình.
- TIME_WINDOW: ETA phải nằm trong [start,end].
- BEFORE_DEADLINE: ETA <= deadline.

## 6. Mục tiêu tối ưu
Thứ tự cứng:
1) giảm số điểm vi phạm cam kết thời gian;
2) trong các phương án cùng mức đúng giờ, giảm tổng km;
3) nếu tiếp tục hòa, giảm tổng thời gian.

## 7. Tải trọng
Nếu vượt `max_weight_kg` hoặc `max_volume_m3`: cảnh báo nhưng cho phép Điều phối lưu/duyệt chuyến.

## 8. Tracking
- Khách xem tọa độ GPS chính xác của xe.
- Link chỉ có dữ liệu của một delivery.
- Sau `DELIVERED`, token hết hạn sau 1 giờ.

## 9. Nhiên liệu
`estimated = distance_km * driving_l_per_100km/100 + idle_hours * idling_l_per_hour`.
Cảnh báo khi chênh lệch tuyệt đối theo phần trăm > 15%.

## 10. Ngoài giờ
Tạo cảnh báo nếu xe nổ máy hoặc di chuyển trong 18:00-07:30, trừ ngoại lệ được duyệt.
