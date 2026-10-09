# M5 POD contract — API 1.5.0

Áp dụng DEC-037/038/039. Snapshot `openapi/m5.openapi.json` bổ sung vào M1–M4, không sửa snapshots cũ. OfflineCommand giữ cấu trúc/required fields và hash command cũ, bổ sung POD_UPLOAD và response PodPhotoOut.

## Upload

POST `/api/v1/deliveries/{deliveryId}/pod/photos`: body bytes JPEG/PNG/WebP, Content-Type tương ứng; Authorization DRIVER. Header X-POD-Metadata là JSON ASCII (Unicode dùng JSON escape `\uXXXX`), tối đa 8192 ký tự. Body bị giới hạn khi streaming. PodMetadata chứa client_action_id, trip_stop_id, source, captured_at có timezone từ app, sha256 trước khi loại EXIF, location_status, GPS fix time/freshness/tọa độ hoặc lý do LOCATION_UNVERIFIED.

Freshness dùng phép tính M1 tại capture/select, không tính theo upload time: ảnh offline không stale chỉ vì upload muộn. EXIF không cung cấp metadata nghiệp vụ. Server bỏ EXIF time/GPS, giữ orientation và compressed pixel data. Lưu original_sha256 và sha256 sau loại EXIF; không watermark/recompress.

201 trả PodPhotoOut; replay nguyên ID/body/metadata trả cùng ảnh. Đổi bytes/metadata/actor bằng ID cũ: 409. Chỉ DRIVER được phân công ở lượt hiện tại, DELIVERING trên trip ACTIVE được tạo ảnh. Retry ảnh đã upload được nhận lại khi trạng thái đã tiến lên; không biến ảnh cũ thành ảnh lượt mới. Conditional PUT và versioning chống version/upload trùng khi mất response hoặc DB rollback.

## Offline

Lưu bytes bền vững theo owner/client_action_id trước khi lưu command. POD_UPLOAD vào outbox M4 theo cùng delivery dependency, rồi mới STATUS DELIVERED. Binary upload thành công rồi POST `/driver/actions` ghi receipt POD_UPLOAD (data=PodMetadata, ID trùng metadata). Upload 409 đi qua command receipt để dùng review/discard/replace DEC-036; không mutate/replay ID mới tự động. Network/5xx giữ nguyên ảnh/command để retry. POD receipt không sinh status event.

## Read và gate

GET `/deliveries/{deliveryId}/pod/photos`: metadata lịch sử theo quyền đọc delivery. GET `/deliveries/{deliveryId}/pod/photos/{photoId}/url`: kiểm tra RBAC rồi cấp signed GET URL đúng version, mặc định 60 giây, ENV tối đa 300 giây. Không public bucket hoặc cache signed URL offline.

DELIVERED cần ít nhất một POD thuộc trip stop hiện tại với version thực, size/hash metadata khớp object. LOCATION_UNVERIFIED có lý do không chặn. POD lịch sử không biết attempt được giữ nhưng không mở gate. Migration 0007 bổ sung cột/index, không suy đoán backfill hoặc sửa 0001–0006.

## Config

POD_MAX_BYTES: 20 MiB; POD_MAX_PIXELS: 40 triệu; POD_READ_URL_SECONDS: 60; S3_PUBLIC_ENDPOINT_URL: endpoint client đọc được (upload vẫn dùng endpoint nội bộ). App giới hạn 20 MiB trước lưu; server xác thực nội dung/định dạng cuối cùng.
