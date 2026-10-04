# M0 FINAL

Ngày: 04/10/2026. Nhánh: `codex/m0-foundation`, tiếp nối M0 tại commit `e028212`.
Health thực tế xác minh lúc `2026-10-04T14:52:42Z` (21:52, UTC+7).
Phạm vi: hoàn thiện và xác minh nền tảng M0; chưa chuyển M1.

## 1. Trạng thái Docker

**PASS.** Docker Desktop Linux Engine hoạt động, Docker Server `29.7.2`. Đã build thành công cả bốn image dự án: MinIO, mc/minio-init, API và admin-web. MinIO/mc dùng source chính thức, giữ release/tag object SHA đã cố định trong Dockerfile.

Đã khởi động Docker Desktop sau khi làm mới thư mục runtime `Docker/run`. Không factory reset, không xóa volume. Không dừng PostgreSQL native hoặc container PostgreSQL của dự án khác. Cổng database dự án chuyển sang `127.0.0.1:55433` để tránh xung đột 5432. Go build giới hạn hai tác vụ, có cache; script build image tuần tự để giảm áp lực RAM.

Bằng chứng: `artifacts/m0-docker-version.txt`, `m0-minio-build.log`, `m0-mc-build.log`, `m0-api-build.log`, `m0-web-build.log`.

## 2. Danh sách service/container và trạng thái

**PASS.** `docker compose up -d --wait --wait-timeout 300` thành công.

| Service / container | Image | Trạng thái | Cổng host loopback |
| --- | --- | --- | --- |
| postgres / fleet-delivery-postgres-1 | postgis/postgis:16-3.5 | Running, healthy | 55433 → 5432 |
| redis / fleet-delivery-redis-1 | redis:7.4-alpine | Running, healthy | 6379 |
| minio / fleet-delivery-minio-1 | fleet-delivery-minio | Running, healthy | 9000, 9001 |
| minio-init / fleet-delivery-minio-init-1 | fleet-delivery-minio-init | Exited (0), hoàn thành đúng nhiệm vụ | — |
| traccar / fleet-delivery-traccar-1 | traccar/traccar:6.10-ubuntu | Running, healthy | 8082, 5055 TCP/UDP |
| api / fleet-delivery-api-1 | fleet-delivery-api | Running, healthy | 8000 |
| admin-web / fleet-delivery-admin-web-1 | fleet-delivery-admin-web | Running, healthy | 3000 |

`minio-init` là job tạo/cấu hình bucket, không phải service phải chạy liên tục. App tài xế là skeleton React Native, không có container server trong Compose.

Bằng chứng: `artifacts/m0-full-stack-start.log`, `artifacts/m0-compose-status.jsonl`.

## 3. Trạng thái database

**PASS trên database thật.** PostgreSQL 16/PostGIS 3.5 nhận kết nối; `PostGIS_Version()` trả `3.5 USE_GEOS=1 USE_PROJ=1 USE_STATS=1`. Đã xác minh 17 bảng nghiệp vụ và phép đo khoảng cách geography thật, cùng ràng buộc từ chối time window không hợp lệ.

17 bảng: users, vehicles, driver_profiles, deliveries, trips, trip_stops, delivery_status_events, pod_photos, tracking_tokens, fuel_profiles, fuel_entries, expenses, maintenance_rules, maintenance_events, vehicle_documents, safety_alerts, audit_logs.

Schema `public` có 19 bảng: 17 bảng nghiệp vụ, `alembic_version`, `spatial_ref_sys`. Các bảng bổ sung trong schema `tiger`/`topology` thuộc extension có sẵn của image PostGIS, không phải thay đổi mô hình nghiệp vụ. Inspector theo search path trả tổng 55 bảng nên không dùng số này làm số bảng nghiệp vụ.

Database test có tên UUID riêng, được tạo cho đúng lần kiểm tra và đã xóa sau khi hoàn tất. Không thử rollback trên database dev/vận hành. Redis PING và storage thật cũng đạt.

## 4. Trạng thái migration

**PASS.** Alembic đã thực thi `upgrade head` trên database dev thật; revision hiện tại là `0001`. API container cũng chạy migration thật trước khi khởi động Uvicorn.

Trên database test riêng: `upgrade head` → toàn bộ pytest → `downgrade base` → `upgrade head` → chạy lại hai integration test, tất cả đạt. SQL baseline giữ nguyên theo byte so với Technical Pack. Không sửa enum, trạng thái, ràng buộc hoặc quy tắc nghiệp vụ.

Đã thêm timeout kết nối Alembic để lỗi mạng được báo có giới hạn; URL dev dùng IPv4 loopback nhằm tránh kết nối localhost bị treo trên Windows.

Bằng chứng: `artifacts/m0-database-verification.log`, `artifacts/m0-container-migration.log`.

## 5. Kết quả test

| Kiểm tra trên trạng thái source cuối | Kết quả |
| --- | --- |
| Pytest toàn bộ backend, database thật | **11 PASS, 0 FAIL, 0 SKIP** |
| Hai integration test database trước đây chưa chạy | **2/2 PASS**, nằm trong 11 test trên |
| Chạy lại integration sau downgrade/upgrade | **2/2 PASS**; không cộng trùng vào tổng test |
| Node test bảo toàn SQL/OpenAPI nguyên bản | **1 PASS, 0 FAIL, 0 SKIP** |
| Backend/scripts Ruff lint + format | PASS, 11 file |
| Mypy strict backend | PASS, 4 file source |
| ESLint web/mobile | PASS |
| Typecheck web/mobile/shared | PASS |
| Next.js production build trong Docker Linux/Node 22 | PASS |
| Expo export Android và iOS sau cài sạch cuối | PASS, hai bundle Hermes khoảng 1.4 MB |
| `npm ci` từ lockfile cuối | PASS |
| `npm audit` trên dependency cuối | **Chưa đạt: 26 mục, 19 high, 7 moderate, 0 critical** |

Tổng test tự động duy nhất: **12 PASS, không có test bị skip**. Không dùng unit mock để thay cho migration, database, storage hoặc Docker thật. Các test health unit vẫn kiểm tra tình huống lỗi bằng mock; các bằng chứng hạ tầng/health trong báo cáo được lấy từ service thực tế.

Đã sửa test `.env.example` để không bị `APP_ENV=test`/`CORS_ORIGINS` của môi trường CI ghi đè nội dung đang được kiểm tra. Khi không có `TEST_DATABASE_URL`, test database bắt buộc FAIL thay vì skip.

Frontend đã đối chiếu với toàn bộ START_HERE V1.1 và UX/UI V1.0, dùng chung design token. Browser thật xác minh 360, 430, 768, 1366, 1440px: không tràn ngang; title 24/32, section 18/28, body 16/24, card radius 12px, padding 16–24px, `lang=vi`. Skeleton mobile dùng title 22/28, body 16/22 và spacing theo spec; export Android/iOS đạt. Chưa quảng bá các màn hình nghiệp vụ hoặc 20 tiêu chí UX của màn hình chưa triển khai là đã nghiệm thu.

Bằng chứng: `artifacts/m0-api-tests.xml`, `m0-database-verification.log`, `m0-frontend-verified.log`, `m0-mobile-verified.log`, `m0-web-build.log`, `m0-npm-ci-verified.log`, `m0-npm-audit-final.json`, `m0-ui-verification.json`.

## 6. Kết quả health check

**PASS trên service thật.**

| Kiểm tra | Kết quả |
| --- | --- |
| PostgreSQL `pg_isready` + truy vấn revision/PostGIS | PASS |
| Redis | PONG |
| MinIO `/minio/health/ready` | Healthy |
| Bucket `fleet-pod` | Private, versioning Enabled |
| MinIO ghi/đọc có xác thực | PASS; object/version test đã xóa |
| Đọc object đó không xác thực | HTTP 403, đúng yêu cầu private |
| Traccar `/api/server` | HTTP 200 |
| API `/health/live` | HTTP 200; request ID UUID hợp lệ |
| API `/health/ready` | HTTP 200, status ready; database/redis/storage/traccar đều true |
| Web `/` | HTTP 200, skeleton tiếng Việt |

Bằng chứng: `artifacts/m0-stack-health.json`, `artifacts/m0-stack-verification.log`. Có thể kiểm tra lại bằng `scripts/verify_stack.py` trong môi trường Python API.

## 7. Trạng thái CI

**CI remote: CHƯA XÁC MINH. Không coi là PASS.** `git remote -v` không có remote; chưa có GitHub Actions run, URL hoặc log server để chứng minh hai job đã chạy.

Workflow YAML đọc được; có hai job frontend/backend, database PostGIS thật, biến `TEST_DATABASE_URL`, lint/typecheck/test/build và migration upgrade/downgrade/upgrade. Đã sửa test cấu hình chịu được `APP_ENV=test` của CI và bổ sung lint/format cho script kiểm tra.

Các bước tương ứng đã kiểm tra local như mục 5, nhưng không thay thế bằng chứng CI remote. Backend test chạy Python 3.12.12 trên Windows; web build chạy Node 22 trong Docker Linux; mobile export local chạy Node 24.15.0. Môi trường GitHub runner chưa được xác minh.

## 8. Các file đã thay đổi

Các thay đổi M0 của lượt tiếp tục này:

- `.env.example`, `compose.yaml`, `scripts/dev.ps1`: cổng database, health MinIO/Traccar, dependency startup và build tuần tự.
- `infra/docker/minio.Dockerfile`, `infra/docker/mc.Dockerfile`: cache Go và giới hạn biên dịch, giữ release/SHA/source chính thức.
- `apps/api/migrations/env.py`: timeout kết nối migration.
- `apps/api/tests/test_database.py`: database test bắt buộc và timeout.
- `apps/api/tests/test_config.py`: tách test env example khỏi biến CI.
- `scripts/verify_database.py`, `scripts/verify_stack.py`: kiểm tra migration/database và stack thật, cleanup tài nguyên test riêng.
- `scripts/verify.ps1`, `.github/workflows/ci.yml`: đưa kiểm tra mới vào quy trình local và lint script trong CI.
- `packages/shared/src/design-tokens.ts`, `packages/shared/src/index.ts`: token UX/UI dùng chung.
- `apps/admin-web/app/layout.tsx`, `apps/admin-web/app/globals.css`, `apps/admin-web/package.json`: áp dụng token, typography, spacing, radius, focus và responsive.
- `apps/driver-mobile/App.tsx`, `apps/driver-mobile/package.json`: token và typography mobile; vẫn chỉ có màn hình khởi tạo.
- `package-lock.json`: đồng bộ dependency workspace shared; không giữ thử nghiệm nâng UUID chưa được xác minh tương thích đầy đủ.
- `README.md`, `docs/adr/0001-foundation.md`, `docs/requirements/M0_TRACEABILITY.csv`, `docs/reports/M0.md`, `docs/reports/M0_UX_UI_REVIEW.md`, `docs/reports/M0_FINAL.md`: hướng dẫn, truy vết, cập nhật trạng thái và báo cáo.

Cập nhật tài liệu từ người dùng được giữ: xóa `START_HERE_FOR_CODEX.md`, dùng `START_HERE_FOR_CODEX_V1.1.md`, bổ sung ZIP và toàn bộ thư mục `UX_UI_Design_Spec_V1.0`. Đã đọc đủ bảy Markdown và DOCX UX/UI; danh sách chi tiết ở `M0_UX_UI_REVIEW.md`.

`.env` local chỉ điều chỉnh host/cổng và thêm `POSTGRES_PORT`; secrets giữ trong file bị Git ignore. Log, JUnit và JSON xác minh nằm trong `artifacts/`, cũng bị ignore. Không thay đổi SQL/OpenAPI baseline, nghiệp vụ khóa hoặc stack kiến trúc.

## 9. Các vấn đề còn tồn tại

**Chặn kết luận M0 PASS:** audit còn 26 mục lan truyền qua ba dependency gốc:

- `braces <=3.0.3`: high, stack exhaustion khi xử lý pattern lồng sâu. [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) hiện chưa có patched version.
- `node-forge <=1.4.0`: high, vấn đề xác minh chữ ký RSA. [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv) hiện chưa có patched version.
- `uuid <11.1.1`: moderate. [GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq) có bản vá, nhưng dependency `xcode@3.0.1` của Expo vẫn yêu cầu UUID 7; chưa giữ được phương án thay thế có cài sạch/graph dependency hợp lệ và tương thích đầy đủ. Trạng thái cuối vẫn có UUID 7.0.3.

Các mục này phần lớn thuộc tooling Expo/Metro/lint. Chưa chứng minh khả năng khai thác trong các route M0; đồng thời chưa có biện pháp xử lý/đánh giá đầy đủ để đóng tiêu chí không còn lỗi nghiêm trọng. Không dùng audit force vì đề xuất hạ Expo SDK xuống 44, không phù hợp stack đã chọn. Không ẩn advisory hoặc tuyên bố audit PASS.

Không phát hiện lỗi chức năng nghiêm trọng còn mở trong migration, các test bắt buộc và stack đã kiểm tra. Có cảnh báo deprecation Starlette/httpx và cảnh báo Node về NO_COLOR/FORCE_COLOR; test/export vẫn đạt, không tắt cảnh báo.

Các điểm tài liệu cho milestone sau vẫn cần thống nhất trước khi code: quyền tài xế hẹn giao lại, ba trạng thái safety alert so với schema hiện tại, cấu hình stale/mất GPS. Chúng chưa được triển khai ở M0; không tự sửa nghiệp vụ để giải quyết.

## 10. Các điểm chưa xác minh

- **CI remote: CHƯA XÁC MINH**, không có Git remote hoặc run trên server.
- Build native APK/IPA, chạy app trên thiết bị/emulator và nghiệm thu UX trên điện thoại; bundle export không thay thế các kiểm tra này.
- Thiết bị GPS thật, tích hợp GPS/đăng nhập/nghiệp vụ và các màn hình M1–M8; ngoài phạm vi M0, chưa triển khai.
- Nghiệm thu production, tải, dự phòng/backup/restore và bảo mật tổng thể của các milestone sau; không suy ra PASS từ dev stack.
- Đóng các advisory dependency ở mục 9 và xác minh lại sau phương án xử lý được chọn.

## 11. Kết luận M0: FAIL

**FAIL — chưa được tuyên bố hoàn tất và chưa chuyển M1.**

Docker Engine, database thật, migration thật, stack đầy đủ, health service chính, toàn bộ 12 test bắt buộc không skip, web/mobile build và đồng bộ UI nền tảng đều đã đạt. SQL/OpenAPI giữ nguyên, không phát hiện code M0 mâu thuẫn nghiệp vụ đã khóa, không thay kiến trúc ngoài phạm vi.

Tiêu chí chất lượng/bảo mật chưa đóng do advisory high/moderate còn tồn tại; CI remote vẫn CHƯA XÁC MINH. Đây là các phần tiếp tục từ trạng thái hiện tại, không cần làm lại M0. Bước tiếp theo: xử lý dependency có bằng chứng tương thích và kiểm tra lại audit/build/test; xác minh CI remote khi repository có remote. Giữ nguyên giới hạn M0 cho đến khi đủ điều kiện PASS.
