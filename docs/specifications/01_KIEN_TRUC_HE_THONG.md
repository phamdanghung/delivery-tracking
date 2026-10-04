# 01 - KIẾN TRÚC HỆ THỐNG

## 1. Kiến trúc đề xuất
Kiến trúc giai đoạn 1 là **modular monolith** để giảm độ phức tạp nhưng vẫn tách module rõ ràng, phù hợp quy mô 1-3 xe và 5-7 điểm giao/ngày hiện tại.

### Thành phần
1. **Web quản trị/Điều phối:** Next.js + TypeScript.
2. **Ứng dụng tài xế:** React Native + TypeScript; có hàng đợi offline cục bộ.
3. **Trang tracking khách:** Next.js route công khai, chỉ truy cập bằng token.
4. **Backend API:** FastAPI + Python 3.12.
5. **Cơ sở dữ liệu:** PostgreSQL + PostGIS.
6. **GPS core:** Traccar Server. Thiết bị GPS 4G gửi dữ liệu trực tiếp vào Traccar.
7. **Redis:** hàng đợi tác vụ nhẹ, khóa chống xử lý trùng, cache ngắn hạn.
8. **Lưu ảnh:** S3-compatible object storage; MinIO cho môi trường dev, S3-compatible production.
9. **Tối ưu tuyến:** OR-Tools trong backend/worker; dữ liệu thời gian/quãng đường lấy qua `RoutingProvider` adapter.
10. **RoutingProvider:** adapter có thể dùng Google Routes/Maps hoặc OSRM; không ràng buộc nghiệp vụ với một nhà cung cấp.

## 2. Luồng dữ liệu GPS
GPS device -> Traccar TCP/UDP -> Traccar DB -> Backend đọc REST/WebSocket -> Web/App/Customer Tracking.
Backend chỉ lưu mapping xe-thiết bị và các snapshot/sự kiện nghiệp vụ cần truy vết; lịch sử GPS thô là trách nhiệm chính của Traccar.

## 3. Module backend
- `auth` - đăng nhập, token, phân quyền.
- `users` - người dùng.
- `fleet` - xe, tài xế, thiết bị, bảo dưỡng.
- `deliveries` - đơn giao, trạng thái, giao lại.
- `trips` - chuyến, điểm dừng, phân xe/tài xế.
- `routing` - geocoding, ma trận, tối ưu tuyến, ETA.
- `gps` - tích hợp Traccar, trạng thái ACC, geofence.
- `pod` - ảnh giao hàng, upload, metadata.
- `tracking` - token/link cho khách.
- `fuel` - định mức, đổ nhiên liệu, đối soát 15%.
- `expenses` - chi phí chuyến.
- `safety` - cảnh báo ngoài giờ, vùng hoạt động, tốc độ nếu có nguồn dữ liệu.
- `reports` - báo cáo nền tảng.
- `audit` - nhật ký thao tác.

## 4. Ranh giới an toàn
- Không có API ngắt/khóa xe từ xa ở Giai đoạn 1.
- Khách chỉ được truy cập endpoint tracking bằng token và chỉ thấy đơn được cấp token.
- Ảnh POD phải ở bucket private.
- Mọi thay đổi trạng thái thủ công quan trọng phải có audit log.

## 5. Môi trường
`local` -> `staging/UAT` -> `production`. Không dùng thiết bị GPS production cho automated tests.
