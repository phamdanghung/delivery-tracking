# M8 — Reports / hardening / recovery / final acceptance

Base: M7 merge `3cefe37fb8c9a334ed98579389662841202d6808`, branch `codex/m8-reporting-hardening`. Canonical runtime `fleet-delivery-dev`, migration head khi bắt đầu `0009`; legacy PRESERVED. Không đổi nghiệp vụ, kiến trúc modular monolith hoặc contract đã khóa.

## Phạm vi được giao

- Reporting WEB-13; security hardening; performance; backup/restore; logging/audit/monitoring; regression toàn hệ thống; acceptance matrix; production readiness review/runbook.
- Áp dụng Technical Pack 07/08/09, UX/UI V1.0 và các DEC M0–M7. Production PASS cần bằng chứng riêng; không suy ra từ local/CI.
- Giữ raw audit/runtime gates; không force fix/downgrade/suppress, không tự mở rộng các accepted risks cũ sang M8/production.
- Tái sử dụng module/tests đã PASS; targeted trước, full regression/build/Docker/CI khi chốt theo CODEX_TOKEN_RULES.md.

## Đang chờ chủ dự án chốt — dừng đúng phần liên quan

1. Reporting: các nhóm WEB-13 và các đề xuất thêm mục 18 Business Spec; RBAC ADMIN/DISPATCHER; cho phép GET/OpenAPI additive.
2. Đúng giờ: ARRIVED hay DELIVERED, kỳ ngày kế hoạch hay ngày sự kiện, đơn hay attempt; cách xử lý thiếu lịch sử cam kết/correction. Không tự định nghĩa KPI hoặc dùng ETA thay thực tế.
3. Vận hành production: deployment target/staging, retention, RPO/RTO. Chưa tự đặt thời hạn xóa backup/ảnh hoặc tuyên bố đạt SLA.

Ba câu hỏi đã gửi ngày 16/10/2026. Không ghi DEC cho đề xuất chưa được phê duyệt. Các phần Docker/security/restore cô lập/quan sát không phụ thuộc vẫn tiếp tục.

## Hướng triển khai trong phạm vi đã rõ

- API: no-store/security headers cho dữ liệu nhạy cảm; log route template, không raw URL/token; chặn public production configuration không an toàn. Không đổi state machine/RBAC/POD/optimization.
- Web runtime: Next standalone multi-stage, giữ build/audit đầy đủ ở builder/CI; kiểm tra dependency thực trong artifact/image. Không coi việc giảm runtime image là đã vá advisory trong tooling.
- Recovery: adapter local tạo backup nhất quán PostgreSQL + MinIO version metadata + Traccar H2 đã dừng ghi; restore drill vào volumes/network mới có ownership label, so fingerprint DB và đọc ảnh/GPS thật. Không restore ghi đè canonical/legacy; không seed nghiệp vụ giả vào canonical.
- Quan sát: đọc log/DB để báo API latency/errors, GPS snapshot age/lag và các chỉ số có bằng chứng. Driver outbox trên thiết bị chưa có server telemetry thì ghi UNKNOWN, không giả backlog bằng 0.
- Acceptance: phân biệt automated API/integration, UI trực quan, thiết bị/GPS ngoài đường, staging/load/production. Hạng mục chưa xác minh không ghi PASS.

Kết quả cuối: `docs/reports/M8_FINAL.md`, acceptance matrix, production blockers, risks và kết luận có bằng chứng. Không deploy/merge hoặc tuyên bố production-ready tự động.
