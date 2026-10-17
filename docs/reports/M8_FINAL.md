# M8 FINAL — Reporting, hardening và acceptance review

Ngày: **17/10/2026**. Source: `9d5afd3fd290256ae01210918181af9e313926e3`, branch `codex/m8-reporting-hardening`; baseline M7 merge `3cefe37fb8c9a334ed98579389662841202d6808`.

## 1. Kết luận hiện tại

**M8: FAIL — chưa được đóng. Production: CHƯA ĐỦ BẰNG CHỨNG / không production-ready.**

Các kiểm tra chức năng CI, targeted Windows và canonical smoke đã PASS; raw npm audit vẫn FAIL và chưa có DEC accepted-risk riêng cho M8. Không mở rộng DEC-050 hoặc các quyết định M0–M6. UI/UAT, thiết bị thật và các production gates bên dưới vẫn chưa được nghiệm thu.

## 2. Phần đã triển khai

- Reporting WEB-13 theo DEC-051–055, chỉ ADMIN: từng attempt EARLY/ON_TIME/LATE/UNKNOWN; tỷ lệ theo eligible_attempts; lịch sử cam kết/ARRIVED/correction truy vết được. Không lấy cam kết hiện tại thay lịch sử lượt cũ.
- Giờ MOVING/IDLING và km Traccar thực; không nối gap hoặc dùng kế hoạch M3. Chất lượng từng KPI VALID/PARTIAL/UNKNOWN, interval/GPS/ACC/mapping có nguồn. Tổng nhiên liệu theo `filled_at`, chi phí theo trip_date; đối soát FINAL/version hiện hành, không grand total chưa có quy tắc chống trùng.
- Web bảng + KPI trong shell hiện có, phân trang/bộ lọc/ngày/xe; BFF chỉ GET reporting. Không public report/POD hoặc đổi RBAC, state machine, optimization objective, contract cũ.
- Security headers/no-store; log JSON theo route template/request ID, không raw tracking URL/token; production configuration guard fail closed. Web image standalone/non-root; API image chỉ COPY nguồn cần chạy.
- Backup local nhất quán DB/MinIO/Traccar; restore vào network/volumes mới có ownership label. Database đích từ template0 để tránh schema PostGIS đã khởi tạo sẵn; không sửa migration hoặc bỏ qua lỗi pg_restore. Quan sát/log review và runbook/readiness checklist đã bổ sung.

## 3. Database, API và file chính

Không có migration M8; head vẫn **0009**, không sửa lịch sử 0001–0009. OpenAPI M8 giữ nguyên **67 paths / 94 schemas M7** và thêm 6 GET dưới `/api/v1/reports`:

`summary`, `attempts`, `vehicles`, `vehicles/{vehicle_id}/intervals`, `financial`, `financial/sources`.

Nguồn chính: `apps/api/app/reporting*.py`, `deployment_policy.py`, `operational_metrics.py`, `apps/admin-web/app/reports/`, BFF và FleetConsole, `infra/docker/{api,web}.Dockerfile`, `scripts/{backup_restore,restore_probe,verify_recovery,operational_review}.py`, `tests/recovery/drill.py`, các test M8 và `openapi/m8.openapi.json`. Quyết định mới: DEC-051–055; không sửa DEC cũ.

## 4. Test/build/CI thực tế

[CI source M8 — run 38979648260](https://github.com/phamdanghung/delivery-tracking/actions/runs/38979648260), đúng source SHA ở đầu báo cáo:

| Kiểm tra | Kết quả |
|---|---|
| Backend lint/format/mypy | PASS |
| Full backend suite | **267 PASS**, không skip test để hoàn tất |
| Downgrade base → upgrade head → integration | **60 PASS**, head0009 |
| Clean npm ci, frontend lint/typecheck | PASS |
| Shared/BFF + mobile queue tests | **10 + 12 PASS** |
| Web build, Android/iOS export | PASS |
| Web/native runtime-surface gates, final non-root web image | PASS; final image kiểm kê 67 packages, không có forbidden package trong gate |
| Python locked-runtime audit | PASS — không phát hiện vulnerability đã biết |
| Raw npm audit | **FAIL — 21 high affected-package findings**, hai advisory gốc chưa vá |
| Backend job / frontend job / toàn workflow | **PASS / FAIL tại raw audit / FAIL** |

Không dùng local test thay CI remote. Bằng chứng local bổ sung: 37 test policy/telemetry PASS; 13 reporting/contract tests PASS trên PostgreSQL thật ngày17/10 sau khi chạy tuần tự; 3 BFF transport test PASS; build web/API và final-image gate PASS. Các lần local lỗi hạ tầng vẫn giữ trong artifacts, không đổi thành PASS.

## 5. Backup/restore và canonical runtime

- CI drill thật PASS: **70 table fingerprints**, head0009, **1 POD private/versioned**, giữ original object version, signed read PASS, anonymous object read403, **1 Traccar device/position**; cleanup đúng source/target cô lập. Thời gian restore-check fixture CI 12.169s không phải RTO production.
- Restore bundle canonical development vào đích mới cũng PASS: 70 fingerprint khớp, head0009, cleanup PASS. Canonical rỗng nên signed POD read/GPS nghiệp vụ không được thực hành trong lượt này; không lấy nó thay drill có dữ liệu thật ở CI.
- Canonical vẫn **fleet-delivery-dev**. Compose sau khởi động lại ngày 17/10: 7 service chính healthy, minio-init exit0. PostgreSQL/PostGIS3.5.2, head0009; Redis PONG; MinIO private/versioning/signed write-read/anonymous403; Traccar200; OSRM matrix/geometry; API live/ready; admin-web và BFF reporting smoke đều **PASS**. Canonical chỉ có1 bootstrap ADMIN, toàn bộ bảng nghiệp vụ được kiểm tra đều0.
- Dữ liệu/runtime/volumes legacy vẫn PRESERVED; chưa phục hồi database cũ, không production data. Không reset/prune/xóa hoặc ghi đè chúng. Không seed nghiệp vụ giả vào canonical.
- Docker Desktop tái lỗi stale `sailor-ingest.sock` khi khởi động; các thư mục IPC đã được đổi tên `.preserved-*`, không xóa. Đã khôi phục Engine29.7.2; workaround chưa chứng minh đã sửa triệt để lỗi Docker Desktop.
- Trong một lượt local build/test đồng thời, PostgreSQL worker exit2 rồi recovery; container không báo OOMKilled/restart. Chưa chứng minh nguyên nhân gốc, không gán cho business logic hay tự khẳng định OOM. Database test duy nhất còn lại đã dọn đúng phạm vi; canonical head0009, vehicles/deliveries/trips đều0 sau recovery. Lượt test bị ngắt không được tính PASS. Sau khi build kết thúc, lượt targeted Windows13 tests và cleanup đã PASS; chưa có bằng chứng tái diễn trong lượt chạy tuần tự cuối.

## 6. Hiệu năng và acceptance matrix

Xem [M8_ACCEPTANCE_MATRIX.md](M8_ACCEPTANCE_MATRIX.md). AT-01–16 có regression tự động trong CI M8; điều đó không thay UI/UAT hoặc thiết bị thật. Giữ nguyên mục tiêu M3/M6 đã khóa, không nới threshold/đổi fixture để làm xanh.

Đo API HTTP trên canonical sau đồng bộ image, 10 lượt đã làm ấm/route: `/vehicles` **5.279ms**, `/deliveries` **6.804ms**, `/reports/summary` **7.815ms** p95, đạt mục tiêu500ms trong phạm vi đo. Bằng chứng `artifacts/m8-canonical-reporting-performance.json`. Dữ liệu canonical rỗng, một người dùng; không chứng minh tải production, telemetry end-to-end5–15s, soak hoặc nhiều thiết bị.

Operational review thực tế vẫn trả `production_ready=false`: DB kết nối không TLS, app role có quyền cao và UPDATE/DELETE/TRUNCATE audit. Log lịch sử container giữ nguyên3 error responses/1 lần DB unavailable/2 lần Traccar unavailable; không báo error rate bằng0. `/health/ready` trong cửa sổ log này p95 **1103ms**, không lấy kết quả warm business reads để che số đó. GPS lag không có mẫu và outbox backlog đều null/UNKNOWN; không giả0. Bằng chứng: `artifacts/m8-final-operational-review.json`.

## 7. Production blockers và rủi ro còn lại

1. Hai advisory chưa vá, chưa có approval M8; mọi approval M0–M7 đều chỉ cho development/local/CI của milestone tương ứng. Chi tiết attack surface/giới hạn: [M8_ACCEPTED_RISKS_REVIEW.md](M8_ACCEPTED_RISKS_REVIEW.md). Review muộn nhất **02/11/2026 hoặc trước production**; upstream patch/runtime exposure phải đánh giá lại ngay.
2. Chưa chốt/kiểm chứng deployment target/staging, domain/TLS/firewall, secrets rotation, DB/storage least privilege và hạn quyền sửa audit. Cấu hình local hiện dùng DB role có quyền cao, không chứng minh production an toàn.
3. Chưa có backup production encrypted/offsite/immutable, daily scheduler/PITR theo provider, retention và RPO/RTO được duyệt/đo thực. Local H2/volume drill không thay rehearsal trên hạ tầng đích.
4. Chưa hoàn tất UI trực quan/UAT, thiết bị Android/iOS/GPS ngoài đường, tải/soak đại diện, log/alert routing/on-call và owner final acceptance. Không tự tiếp tục Computer Use đã bị dừng trước đó.
5. Chưa có scan OS/base image/native binary/vendored code đầy đủ. Package/source-map gates không chứng minh toàn bộ production attack surface không có vulnerability; Docker Desktop và sự cố local DB ở trên cần theo dõi riêng.

Quy trình trước production: [PRODUCTION_READINESS.md](../operations/PRODUCTION_READINESS.md); phục hồi local: [RECOVERY_RUNBOOK.md](../operations/RECOVERY_RUNBOOK.md).

## 8. Deferred và quyết định cần chủ dự án

- Reporting Business Spec mục18 ngoài WEB-13: deferred/chưa đủ contract/quyền/công thức; không tự thêm KPI/dữ liệu giả. Harsh braking/out-of-area vẫn theo DEC-048; không remote immobilization.
- Cần quyết định accepted-risk riêng cho M8 nếu chủ dự án muốn tiếp tục nghiệm thu development/local/CI với hai advisory còn tồn tại. Không được xem là đã vá hoặc cho production.
- Cần chốt hạ tầng/SLA/retention và kế hoạch UAT/thiết bị/nghiệm thu trước release. Không tự merge, deploy production hoặc mở rộng milestone.

## 9. Chạy kiểm tra lại khi có thay đổi liên quan

`docker compose -p fleet-delivery-dev ps`; chạy `scripts/verify_stack.py`, `scripts/verify_osrm.py` bằng môi trường Python API. Targeted DB/contract: `scripts/verify_database.py --focused tests/test_m8_reporting_api.py tests/test_contract.py`. Full regression/export/restore và audit xem workflow M8; không lặp toàn bộ khi source/bằng chứng còn nguyên theo CODEX_TOKEN_RULES.md.
