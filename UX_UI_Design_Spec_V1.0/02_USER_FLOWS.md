# 02 - USER FLOWS

## 1. Luồng Điều phối - từ Zalo tới chuyến giao
1. Nhân viên mở **Tạo đơn**.
2. Dán nội dung nhận từ Zalo vào ô nháp.
3. Hệ thống hỗ trợ tách gợi ý: khách, SĐT, địa chỉ, thời gian hẹn, ghi chú.
4. Người dùng kiểm tra và chỉnh lại dữ liệu; không tự lưu dữ liệu tách sai.
5. Lưu đơn ở trạng thái **Mới tạo**.
6. Chọn nhiều đơn trong danh sách -> **Tạo chuyến**.
7. Chọn xe, tài xế, điểm đầu/cuối.
8. Nếu vượt tải trọng -> hiển thị cảnh báo, vẫn cho tiếp tục.
9. Bấm **Tối ưu tuyến**.
10. Hệ thống trả thứ tự điểm, ETA, km, thời gian và cảnh báo nguy cơ trễ.
11. Điều phối xem/điều chỉnh -> **Duyệt chuyến**.
12. Tài xế nhìn thấy chuyến trên app.

## 2. Luồng tài xế - giao thành công
1. Mở app -> **Hôm nay**.
2. Xem điểm đang phục vụ và điểm tiếp theo.
3. Mở chi tiết điểm -> xem khách, SĐT, địa chỉ, giờ hẹn, ghi chú.
4. Bấm **Mở chỉ đường**.
5. Khi xe vào bán kính 50 m -> hệ thống tự ghi **Đã đến**.
6. Nếu nhận sai, tài xế có thể sửa trạng thái; bắt buộc nhập lý do.
7. Bấm **Bắt đầu bàn giao**.
8. Chụp ít nhất 1 ảnh bằng chứng.
9. Bấm **Giao thành công**.
10. Nếu offline -> UI báo "Đã lưu trên máy - chờ đồng bộ"; không mất dữ liệu.
11. Điểm tiếp theo tự nổi bật.

## 3. Luồng tài xế - giao thất bại
1. Từ chi tiết điểm -> **Giao không thành công**.
2. Chọn/nhập lý do bắt buộc.
3. Chọn **Hẹn giao lại**.
4. Nhập ngày/giờ cam kết mới.
5. Xác nhận.
6. Đơn quay lại danh sách cần điều phối theo nghiệp vụ.

## 4. Luồng sửa "Đã đến" nhận sai
1. Mở đơn đang có trạng thái **Đã đến**.
2. Chọn **Sửa trạng thái**.
3. UI hiển thị cảnh báo: thao tác sẽ được ghi nhật ký.
4. Chọn trạng thái mới hợp lệ.
5. Nhập lý do bắt buộc.
6. Xác nhận.
7. Giao diện hiển thị người sửa + thời điểm trong timeline.

## 5. Luồng tracking khách
1. Nhân viên copy link tracking và gửi Zalo thủ công.
2. Khách mở link.
3. Nếu hợp lệ: thấy trạng thái + ETA + vị trí GPS chính xác + thời gian cập nhật.
4. Sau giao thành công, link còn xem được tối đa 1 giờ.
5. Hết hạn -> chỉ hiển thị thông báo "Liên kết đã hết hiệu lực"; không hiển thị vị trí xe.

## 6. Luồng cảnh báo nhiên liệu
1. Tài xế/nhân viên nhập lần đổ nhiên liệu + số lít + ảnh hóa đơn nếu có.
2. Hệ thống so với mức ước tính.
3. Nếu chênh lệch >15% -> badge/cảnh báo nổi bật.
4. Người có quyền mở chi tiết để xem số liệu và ghi chú xử lý.

## 7. Luồng mất mạng App tài xế
1. Banner "Đang ngoại tuyến" xuất hiện nhưng không chặn thao tác cần thiết.
2. Dữ liệu chuyến đã tải vẫn xem được.
3. Ảnh/trạng thái được lưu cục bộ vào hàng đợi.
4. Mỗi thao tác có trạng thái: Chờ đồng bộ / Đang đồng bộ / Đã đồng bộ / Lỗi.
5. Khi có mạng, app tự đồng bộ.
6. Nếu lỗi, cho phép **Thử lại**, không tạo bản ghi trùng.
