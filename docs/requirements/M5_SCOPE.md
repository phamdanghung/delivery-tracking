# M5 — e-POD bằng ảnh

Branch `codex/m5-e-pod`, base M4 merge `32cd5872507dd3f9a56a059c2c0ff7086e87e8eb`.

Áp dụng POD-01/02, DEC-017/020/036, AT-07/08, UX DRV-05/WEB-08. Giữ FastAPI modular monolith, Expo SDK 57/React Native 0.86, SQLite/outbox M4 và private S3-compatible/MinIO. Không thay migrations lịch sử hoặc snapshots contract M1–M4.

- Camera/album theo permission, preview và metadata đúng delivery; lưu ảnh trên thiết bị trước khi báo đã lưu, phục hồi sau restart/offline/reconnect.
- Ảnh là đủ; không bắt buộc chữ ký. Offline DELIVERED chỉ là kết quả đã lưu trên máy/chờ đồng bộ; server vẫn yêu cầu object POD hợp lệ trước khi ghi DELIVERED.
- Upload chỉ DRIVER được phân công; ADMIN/DISPATCHER xem bằng chứng theo quyền hiện có. Không public bucket/object hoặc cho khách truy cập POD trong M5. Validate bytes/MIME/size/hash; object immutable và metadata/idempotency chống retry tạo ảnh/version/event trùng.
- Web detail hiển thị bằng chứng và metadata; signed read URL ngắn hạn chỉ cấp sau kiểm tra RBAC. API/schema M5 bổ sung có phiên bản cho endpoint POD đã có trong Technical Pack; không sửa contract baseline.
- Không Customer Tracking/ETA M6, chi phí/bảo dưỡng M7 hoặc các workflow ngoài M5.

## Quyết định M5 đã chốt

1. DEC-037: GPS thiếu/stale/invalid vẫn cho lưu/upload/DELIVERED; LOCATION_UNVERIFIED cần lý do xác nhận và audit. GPS hợp lệ lưu fix time/freshness/status. Không tạo tọa độ giả hoặc dùng GPS cũ như vị trí hiện tại.
2. DEC-038: CAMERA_CAPTURED/ALBUM_SELECTED; metadata nghiệp vụ từ app/server, không tin EXIF time/GPS. Bỏ EXIF không cần thiết nhưng giữ orientation/rendering và audit nguồn ảnh.
3. DEC-039: POD gắn trip stop/lượt giao hiện tại; lượt mới sau reschedule cần POD mới; giữ POD cũ để truy vết.

Triển khai tiếp từ nền tảng kiểm tra ảnh và object immutable hiện có, không làm lại M4. **DEC-040** phê duyệt riêng hai advisory tooling cho M5 development/local/CI; giữ audit/runtime gates và đầy đủ điều kiện/review deadline, không áp dụng production. **DEC-041** chọn **fleet-delivery-dev** làm canonical development runtime, reuse volumes và chỉ migrate tiến lên ở milestone sau; fleet-delivery head 0005 giữ PRESERVED/LEGACY. Không merge PR #4, không chuyển M6.
