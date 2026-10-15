# Production readiness — M8

Trạng thái: **chưa phê duyệt production**. `fleet-delivery-dev` là canonical development theo DEC-041, không phải cấu hình production mẫu.

## Release và kiểm tra trước triển khai

1. Chốt môi trường đích, domain/TLS, tải dự kiến, thiết bị/UAT, người vận hành và tiêu chí rollback với chủ dự án.
2. Dùng đúng commit/lockfiles đã có bằng chứng CI và acceptance matrix; ghi image digest. Không dùng development accepted risk như phê duyệt production.
3. Review `M8_ACCEPTED_RISKS_REVIEW.md`, raw npm/Python audit và runtime-surface gates. Có bản vá upstream hoặc exposure mới thì đánh giá lại trước release.
4. Tách role chạy ứng dụng khỏi role migration/backup; hạn chế quyền DB và quyền sửa/xóa audit. Xác minh TLS của kết nối thực, không chỉ tên ENV.
5. Cấp secrets riêng qua cơ chế của môi trường triển khai; xoay credential bootstrap, kiểm tra refresh/revoke/RBAC. Không đưa `.env`, dump, token, signed URL hoặc địa chỉ khách vào log/repository.
6. Chỉ public ingress HTTPS của web/API và phần object storage cần cho signed URL; DB/Redis/MinIO admin/Traccar admin/OSRM ở mạng private. CORS chỉ đúng origin được duyệt. `APP_ENV=production` kiểm tra cấu hình tối thiểu và fail closed; vượt qua kiểm tra này **không** chứng minh production ready.
7. Thiết lập backup DB hằng ngày/PITR theo provider, POD versioning/private, backup Traccar theo backend thực. Chốt retention/RPO/RTO, mã hóa/offsite/key recovery và người nhận cảnh báo. Chạy restore rehearsal bằng đúng hạ tầng đích trước production.
8. Chạy migration bằng quyền phù hợp, kiểm tra head, liveness/readiness, private storage/versioning và smoke test RBAC/tracking/POD. Không sửa migration lịch sử. Nếu migration lỗi: dừng rollout, giữ bằng chứng; không tự downgrade hoặc restore ghi đè dữ liệu.
9. Đo p95 trên cấu hình/tải đại diện và GPS end-to-end bằng thiết bị thật. Không dùng health endpoint, DB rỗng hoặc local TestClient để suy ra tải production.
10. Chủ dự án nghiệm thu và cho phép release sau khi đóng blockers trong `M8_FINAL.md`. Chưa có lệnh deploy trong M8 hiện tại.

## Giám sát và audit

- JSON log có request ID, route template, status, duration; không log raw tracking token/query/body/header bí mật. Thu gom bền vững, hạn quyền truy cập và kiểm thử redaction ở ingress/reverse proxy nữa.
- `scripts/operational_review.py` đọc cấu hình/DB/log, báo riêng lỗi API, lỗi tối ưu/upload, trạng thái snapshot GPS và lag có mẫu. `--require-production-ready` trả lỗi khi chưa có bằng chứng readiness.
- Driver outbox là dữ liệu thiết bị: log server không chứng minh backlog bằng 0. Cần cơ chế quan sát và quy trình hỗ trợ thiết bị được duyệt trước vận hành rộng.
- Chốt alert routing/on-call, ngưỡng theo môi trường và retention log/audit; không tự đặt thời hạn xóa dữ liệu.
- Audit nghiệp vụ trong DB và backup fingerprints không chứng minh chống sửa bởi DB superuser. Cần least privilege/thu gom audit độc lập hoặc cơ chế được môi trường đích phê duyệt.

## Sự cố và rollback

- Liveness lỗi: xác minh tiến trình/tài nguyên; readiness lỗi: kiểm tra từng dependency, không chuyển sang mock/fallback khoảng cách hoặc GPS giả.
- Giữ image trước release và backup nhất quán đã thử khôi phục. Rollback code chỉ khi tương thích schema; nếu không, cần quyết định vận hành với backup/recovery đã xác minh. Không tự restore đè canonical/production.
- Runbook local: [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md). Adapter này không bao phủ managed DB/PITR, production Traccar khác H2, object storage ngoài local hoặc automatic failover.

## Bằng chứng còn phải cung cấp từ môi trường đích

TLS/ingress thực; firewall; secret rotation; DB least privilege/audit retention; offsite/encrypted backups/PITR và RPO/RTO đo thực; tải/soak; thiết bị Android/iOS/GPS ngoài đường; UI/UAT; log/alert delivery; owner final acceptance. Các mục này không được ghi PASS chỉ vì CI xanh.
