# M8 — Reports / hardening / recovery / final acceptance

Base: M7 merge `3cefe37fb8c9a334ed98579389662841202d6808`, branch `codex/m8-reporting-hardening`. Canonical runtime `fleet-delivery-dev`, migration head khi bắt đầu `0009`; legacy PRESERVED. Không đổi nghiệp vụ, kiến trúc modular monolith hoặc contract đã khóa.

## Phạm vi được giao

- Reporting WEB-13; security hardening; performance; backup/restore; logging/audit/monitoring; regression toàn hệ thống; acceptance matrix; production readiness review/runbook.
- Áp dụng Technical Pack 07/08/09, UX/UI V1.0 và các DEC M0–M7. Production PASS cần bằng chứng riêng; không suy ra từ local/CI.
- Giữ raw audit/runtime gates; không force fix/downgrade/suppress, không tự mở rộng các accepted risks cũ sang M8/production.
- DEC-056 chấp nhận riêng hai advisory cho M8 development/local/CI; không production/không coi đã vá, giữ raw audit và runtime gates cùng mọi giới hạn UAT/production. Review muộn nhất 02/11/2026 hoặc trước production; patch/runtime exposure phải đánh giá lại.
- Tái sử dụng module/tests đã PASS; targeted trước, full regression/build/Docker/CI khi chốt theo CODEX_TOKEN_RULES.md.

## Reporting đã chốt

- DEC-051: WEB-13, chỉ ADMIN, GET additive/OpenAPI; không mutation. Các nhóm mục 18 thiếu contract ghi deferred.
- DEC-052/053: ARRIVED cuối cùng còn hiệu lực theo attempt, cam kết/lịch sử tương ứng; trip_date/timezone hệ thống. EARLY/ON_TIME/LATE riêng; eligible_attempts là tổng ba nhóm, tỷ lệ từng nhóm trên eligible_attempts; UNKNOWN riêng và loại khỏi mẫu số. Trace trip/delivery/attempt/commitment/event/correction.
- DEC-054: giờ MOVING/IDLING và km Traccar thực đã xác minh; không nối gap, không dùng M3 thay thực tế. Chất lượng từng KPI VALID/PARTIAL/UNKNOWN, coverage và nguồn/interval truy vết được.
- DEC-055: nhiên liệu theo filled_at M7 (ngày đổ), chi phí theo trip_date; tổng tiền hai nguồn riêng, chưa có grand total do thiếu quy tắc chống trùng. Đối soát FINAL/version hiện hành, không cộng lịch sử hoặc tự phân bổ kỳ.

## Đang chờ chủ dự án chốt — dừng đúng phần liên quan

1. Vận hành production: deployment target/staging, retention, RPO/RTO. Chưa tự đặt thời hạn xóa backup/ảnh hoặc tuyên bố đạt SLA.

Các câu hỏi reporting ngày 16/10/2026 đã được chủ dự án chốt bằng DEC-051 đến DEC-055. Không ghi DEC cho đề xuất chưa được phê duyệt; tiếp tục triển khai đúng phạm vi đã chốt.

## Hướng triển khai trong phạm vi đã rõ

- API: no-store/security headers cho dữ liệu nhạy cảm; log route template, không raw URL/token; chặn public production configuration không an toàn. Không đổi state machine/RBAC/POD/optimization.
- Web runtime: Next standalone multi-stage, giữ build/audit đầy đủ ở builder/CI; kiểm tra dependency thực trong artifact/image. Không coi việc giảm runtime image là đã vá advisory trong tooling.
- Recovery: adapter local tạo backup nhất quán PostgreSQL + MinIO version metadata + Traccar H2 đã dừng ghi; restore drill vào volumes/network mới có ownership label, so fingerprint DB và đọc ảnh/GPS thật. Không restore ghi đè canonical/legacy; không seed nghiệp vụ giả vào canonical.
- Quan sát: đọc log/DB để báo API latency/errors, GPS snapshot age/lag và các chỉ số có bằng chứng. Driver outbox trên thiết bị chưa có server telemetry thì ghi UNKNOWN, không giả backlog bằng 0.
- Acceptance: phân biệt automated API/integration, UI trực quan, thiết bị/GPS ngoài đường, staging/load/production. Hạng mục chưa xác minh không ghi PASS.

Kết quả cuối: `docs/reports/M8_FINAL.md`, acceptance matrix, production blockers, risks và kết luận có bằng chứng. Không deploy/merge hoặc tuyên bố production-ready tự động.
