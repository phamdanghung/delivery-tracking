# 01 - KIẾN TRÚC THÔNG TIN

## 1. Nguyên tắc điều hướng
Web dùng **sidebar cố định + topbar**, không dùng menu nhiều tầng sâu. Tối đa 2 cấp điều hướng.

### Sidebar Web
1. **Tổng quan**
2. **Điều phối giao hàng**
   - Đơn giao
   - Chuyến giao
   - Tối ưu tuyến
3. **Xe & GPS**
   - Bản đồ trực tiếp
   - Lịch sử hành trình
4. **Vận hành**
   - Nhiên liệu & chi phí
   - Bảo dưỡng & giấy tờ
   - Cảnh báo an toàn
5. **Báo cáo**
6. **Quản trị**
   - Người dùng & phân quyền
   - Cấu hình

### Topbar Web
- Ngày làm việc hiện tại.
- Ô tìm nhanh theo mã đơn / tên khách / biển số.
- Trạng thái hệ thống/GPS.
- Thông báo.
- Tài khoản.

## 2. Cấu trúc App tài xế
App tài xế không bê nguyên sidebar web sang mobile.

### Điều hướng chính
- **Hôm nay**: chuyến hiện tại và các điểm giao.
- **Chi phí**: nhập chi phí phát sinh.
- **Tài khoản**: thông tin tài xế, trạng thái đồng bộ, đăng xuất.

Tác vụ quan trọng như giao thành công/thất bại nằm ngay trong **Chi tiết điểm giao**, không đặt ở menu riêng.

## 3. Tracking khách
Không có menu. Một link chỉ phục vụ một đơn.

Cấu trúc:
- Trạng thái đơn.
- ETA.
- Bản đồ xe.
- Thời gian cập nhật GPS.
- Thông tin liên hệ cần thiết.

## 4. Hệ phân cấp thông tin
### Mức 1 - cần thấy ngay
- Trễ/đúng giờ.
- Xe đang ở đâu.
- Điểm tiếp theo.
- Đơn nào có vấn đề.
- Trạng thái GPS/offline.

### Mức 2 - cần khi xử lý
- Chi tiết khách.
- Khung giờ hẹn.
- tải trọng.
- ảnh giao.
- timeline trạng thái.

### Mức 3 - lịch sử/quản trị
- audit log.
- lịch sử hành trình.
- lịch sử nhiên liệu.
- cấu hình bảo dưỡng.

## 5. Quy ước URL đề xuất
- `/dashboard`
- `/deliveries`
- `/deliveries/new`
- `/deliveries/{id}`
- `/trips`
- `/trips/{id}`
- `/trips/{id}/optimize`
- `/fleet/live`
- `/fleet/vehicles/{id}/history`
- `/operations/fuel`
- `/operations/maintenance`
- `/operations/alerts`
- `/reports`
- `/admin/users`
- `/t/{trackingToken}` - tracking khách
