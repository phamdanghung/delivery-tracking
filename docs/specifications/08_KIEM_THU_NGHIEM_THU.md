# 08 - KIỂM THỬ NGHIỆM THU

## AT-01 GPS trực tiếp
Thiết bị gửi dữ liệu -> web hiển thị vị trí, tốc độ, hướng, ACC và thời gian cập nhật.

## AT-02 GPS cũ/mất tín hiệu
Không được hiển thị vị trí cũ như vị trí hiện tại; phải có nhãn mất kết nối/cập nhật lần cuối.

## AT-03 Tạo 7 điểm giao
Nhập 7 đơn, đủ 3 kiểu cam kết thời gian, lập được một chuyến.

## AT-04 Tối ưu ưu tiên đúng giờ
Tạo dữ liệu sao cho tuyến ngắn nhất làm trễ 1 khách nhưng tuyến dài hơn đáp ứng tất cả; hệ thống phải chọn phương án đúng giờ.

## AT-05 Geofence 50 m
Giả lập xe đi từ ngoài vào trong 50 m -> đơn tự sang ARRIVED một lần.

## AT-06 Sửa ARRIVED
Tài xế/Điều phối sửa trạng thái -> bắt buộc lý do và sinh audit log trước/sau.

## AT-07 POD bắt buộc ảnh
Không ảnh -> không được DELIVERED; có ảnh -> được hoàn tất.

## AT-08 Offline POD
Mất mạng, chụp ảnh và hoàn tất -> queue; có mạng -> đồng bộ đúng một lần, không trùng.

## AT-09 Giao thất bại/giao lại
FAILED bắt buộc lý do; reschedule bắt buộc cam kết thời gian mới và quay lại danh sách điều phối.

## AT-10 Tracking privacy
Token A không truy cập được delivery B; khách thấy GPS chính xác của xe nhưng không thấy khách khác.

## AT-11 Tracking expiry
Sau DELIVERED + 1 giờ -> endpoint public trả 410.

## AT-12 Vượt tải
Vượt tải -> cảnh báo rõ, vẫn cho Điều phối lưu chuyến.

## AT-13 Nhiên liệu
Variance 14.9% không cảnh báo; 15% không cảnh báo; 15.1% cảnh báo.

## AT-14 Ngoài giờ
17:59 không cảnh báo; 18:00 cảnh báo; 07:29 cảnh báo; 07:30 không cảnh báo, trừ ngoại lệ.

## AT-15 Bảo dưỡng riêng từng xe
Hai xe có interval khác nhau -> cảnh báo theo rule từng xe.

## AT-16 Không có remote immobilization
UI/API không tồn tại chức năng ngắt/khóa xe.
