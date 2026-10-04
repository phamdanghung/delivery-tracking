# 07 - BẢO MẬT, HIỆU NĂNG VÀ VẬN HÀNH

## Bảo mật
- HTTPS/TLS toàn bộ production.
- JWT access ngắn hạn + refresh rotation hoặc session an toàn.
- Password hash Argon2id/bcrypt.
- Phân quyền server-side; không tin quyền từ giao diện.
- Tracking token ngẫu nhiên >=128 bit, chỉ lưu hash trong DB.
- Bucket ảnh private, cấp signed URL ngắn hạn.
- Rate limit public tracking.
- Validate MIME/size ảnh; không cho upload tùy ý.
- Audit các thay đổi trạng thái, route override, sửa “Đã đến”, cấu hình xe/nhiên liệu.

## Hiệu năng mục tiêu
- API thông thường p95 < 500 ms trong điều kiện nội bộ bình thường.
- Live map phản ánh dữ liệu GPS với mục tiêu 5-15 giây khi thiết bị/mạng hoạt động.
- Tối ưu <= 3 xe, <= 30 điểm: mục tiêu trả kết quả trong 5 giây; nếu quá 10 giây phải hiển thị đang xử lý.
- Tracking khách p95 < 1 giây nếu cache/live source sẵn sàng.

## Offline
- Driver app dùng local SQLite/secure storage + outbox queue.
- Mọi command offline có `client_action_id` duy nhất.
- Server idempotency trong tối thiểu 24 giờ.

## Sao lưu
- DB backup hằng ngày + PITR nếu nhà cung cấp hỗ trợ.
- Ảnh POD có versioning/retention.
- Kiểm thử restore định kỳ.

## Quan sát hệ thống
Metrics: GPS ingest lag, số thiết bị offline, API error, queue backlog, route optimizer failures, upload failures.
Logs JSON có `request_id`, không ghi mật khẩu/token đầy đủ.
