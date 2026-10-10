# M6 FINAL — Customer tracking / ETA

Cập nhật: 10/10/2026. **Kết luận: FAIL — chưa có phê duyệt accepted risk cho M6.** Không merge PR #5, không chuyển M7.

## 1. Phần đã triển khai

- Áp dụng DEC-042/043/044/045; token 256 bit theo delivery attempt/trip stop/xe, chỉ hash trong DB. ADMIN/DISPATCHER cấp nhiều link và thu hồi từng link idempotently, có audit; plaintext chỉ trả lần tạo. Nhân viên copy/gửi Zalo thủ công.
- Trang `/t/{trackingToken}` mobile-first: mã/trạng thái đơn, đúng GPS xe được phép và ETA. Không trả khách/đơn/xe khác, toàn tuyến, lịch sử, POD, phone/notes/actor hoặc ID nội bộ.
- DELIVERED hết hạn đúng +1 giờ; trong giờ đó chỉ thông tin hoàn tất, không GPS/ETA live. FAILED/CANCELLED/RESCHEDULED, đổi lượt/xe, revoked hoặc expired làm link không còn hiệu lực, trả 410 chung.
- ETA dùng GPS fresh, OSRM self-host, các điểm chưa hoàn tất/service time/cửa sổ hẹn của tuyến đã duyệt; cache 10s, vẫn kiểm tra lifecycle, toàn bộ stop/sequence và tọa độ/thời gian hẹn hiện hành với snapshot đã duyệt trước khi dùng cache. Mỗi request xác minh OSRM thật, không cache che lỗi provider; dữ liệu tuyến sai khác trả UNKNOWN. GPS/OSRM lỗi không tạo ETA giả. DELIVERED trả sớm, không đọc GPS/tính ETA mới hoặc hiển thị ETA cũ. Xe có nhiều chuyến ACTIVE: ẩn GPS/ETA vì không xác định chắc chuyến đang phục vụ; không sửa quy tắc M2.
- Anonymous BFF không chuyển cookie/Authorization nội bộ; Redis peer/token rate limits fail closed; no-store/no-referrer/noindex, không log raw token. Không gửi tự động SMS/ZNS, không geocode/provider ngoài, không làm M7.

## 2. File / migration / API chính

`apps/api/app/tracking*.py`, hook `deliveries.event`, `0008_m6_tracking.py`; `apps/admin-web/app/t`, `app/tracking`, `app/api/public/tracking`, component cấp/copy/thu hồi trong delivery detail; ENV/Compose/CI; `M6_SCOPE.md`, DEC-042/043/044/045 và `openapi/m6.openapi.json`.

API: `POST /api/v1/tracking-links`, `POST /api/v1/tracking-links/{identifier}/revoke`, `GET /api/v1/public/tracking/{token}`. Không thêm endpoint lấy lại plaintext. Migration additive 0008; 0001–0007 và contract M1–M5 giữ nguyên, compatibility tests PASS. Expo SDK/React Native/dependency lockfiles không đổi.

Source cuối: `655a02c0b44880e4ef21232a00f9473fb2aa6c70`, branch `codex/m6-customer-tracking-eta`, base M5 merge `a6438c903b4eae278a4bc99be3de89d71d19b5fd`. [Draft PR #5](https://github.com/phamdanghung/delivery-tracking/pull/5).

## 3. Test / build / Docker / CI

| Kiểm tra | Bằng chứng / kết quả |
|---|---|
| Backend lint / format / mypy | PASS; 28 module typed |
| Regression local trước guard bổ sung | 121 PASS; downgrade base → upgrade head → 36 integration PASS (`artifacts/m6-database-full-rerun.log`) |
| M6 source trước DEC-045, database/Redis/OSRM/MinIO thật | 11 integration PASS (`artifacts/m6-focused-final.log`), gồm isolation, RBAC/hash/audit, nhiều link/revoke concurrent, expiry/replay, completed privacy, failed/reschedule/lượt mới, GPS stale/missing/future, OSRM/Redis unavailable, rate limit, multi-stop ETA/cache p95 <1s và serving-trip ambiguity. Redis concurrency test riêng PASS |
| Frontend local | lint/typecheck PASS; 7 shared +10 mobile tests PASS; web build PASS |
| Clean npm ci / web / Android+iOS export | PASS trong CI `762d6a8` và source cuối `655a02c`; Docker web clean npm ci/build PASS, không thay dependencies |
| Runtime surface | web 21 traces không chứa advisory packages; Android/iOS source maps 1313/1179 sources không chứa advisory packages; gates PASS trong CI |
| Migration canonical | head **0008**, PostGIS 3.5.2; bootstrap ADMIN duy nhất, business tables và tracking_tokens đều 0 |
| Canonical Docker | **fleet-delivery-dev**; PostgreSQL/PostGIS, Redis, MinIO, Traccar, OSRM, API, admin-web healthy; minio-init exited 0; API live/ready 200, web 200, Redis PONG, Traccar 200, OSRM matrix/road geometry PASS; MinIO versioning Enabled, signed write/read PASS, anonymous read 403 |
| Legacy / test cleanup | fleet-delivery và volumes/runtime/data disk cũ được giữ PRESERVED; không migrate/reset/prune/xóa. Chỉ cleanup DB/bucket riêng do test tạo; canonical không seed dữ liệu nghiệp vụ giả |
| Public web smoke | canonical page 200; anonymous BFF 410 cho token không hợp lệ, no-store/no-referrer/noindex. CUS-03 mobile 390px không tràn ngang/không render GPS |
| CI remote source đầu | [Run 37942759694](https://github.com/phamdanghung/delivery-tracking/actions/runs/37942759694), `cdc3fa2`: backend PASS (121 +36 integration, migration round-trip); frontend chỉ FAIL tại npm audit, mọi bước build/export/test/runtime gate trước đó PASS. Đã đọc log job thực tế |
| CI remote trước DEC-045 | [Run 37944693897](https://github.com/phamdanghung/delivery-tracking/actions/runs/37944693897), `762d6a8`: **backend PASS**, 122 test +37 integration và migration round-trip; **frontend FAIL duy nhất tại npm audit**, mọi bước npm ci/lint/typecheck/test/build/export/runtime gates trước đó PASS. Đã xác minh status job và log thực tế trên đúng source cuối |

| CI remote source cuối DEC-045 | [Run 38051420473](https://github.com/phamdanghung/delivery-tracking/actions/runs/38051420473), `655a02c`: **backend PASS — 125 test +40 integration sau migration round-trip**. **Frontend FAIL duy nhất npm audit**; npm ci/lint/types/test/web build/Android+iOS export/runtime gates PASS. Đã đọc status và log thực tế |
| Local bổ sung DEC-045 | lint/format/mypy PASS. Hai lượt focused không đạt: fixture M3 tối ưu 4 stop trả 422 “không tìm được tuyến đầy đủ” trước khi kiểm tra tracking; không đổi solver/ngưỡng/skip test. Các test mới đổi tọa độ/giờ hẹn/sequence với warm cache và OSRM unavailable đã PASS trong full CI Linux đúng source cuối |
| Runtime sau DEC-045 | Engine 29.7.2 hoạt động; chỉ rebuild API và restart canonical. 7 services healthy; head 0008, bootstrap/login/list rỗng PASS; private/versioned MinIO và API live/ready PASS. Legacy containers/volumes/data disk giữ nguyên. IPC socket lỗi được lưu riêng `.preserved-m6-20261010`/`-attempt2`; không reset/prune/delete |

Lượt local đầu 119 PASS/2 FAIL khi Docker build/export đang chạy: M3 30-stop 5.093s vượt ngưỡng 5s và Traccar feed timeout. Rerun sau build PASS 121 +36; không nới ngưỡng, không bỏ test hoặc thay bằng mock.

Bằng chứng local: `artifacts/m6-canonical-verification.json`, `m6-focused-final.log`, `m6-database-full-rerun.log`, `m6-docker-build.log`, `m6-api-final-build.log`, `m6-web-build.log`, `m6-web-surface.json`, `m6-npm-audit.json`, `m6-final-health.json`, `m6-compose-state.json`; health/OSRM scripts kiểm tra runtime thật. Log CI source cuối DEC-045: `m6-ci-frontend.log`, `m6-ci-backend.log`. Bằng chứng bổ sung: `m6-dec045-tests.log`, `m6-dec045-tests-rerun.log`, `m6-dec045-api-build.log`, `m6-dec045-health.log`, `m6-dec045-canonical.log`, `m6-dec045-containers.json`. Artifacts được ignore, không đưa credentials vào Git.

## 4. Security advisory / quyết định cần chủ dự án

`npm audit`: **21 high findings**, từ hai advisory chưa vá:

- [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
- [node-forge GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv).

Dependency tree/triage M5 còn áp dụng vì lockfiles không đổi; M6 kiểm tra lại audit và built runtime surface bằng log CI thật. Không thấy packages này trong web/native artifacts đã kiểm tra; rủi ro còn ở tooling xử lý pattern/repo/config/cert. Không coi đó là bản vá hoặc phê duyệt production. Audit đề xuất Expo 44.0.6 là downgrade phá stack, không áp dụng.

DEC-040 chỉ chấp nhận M5; **M6 chưa được phê duyệt**. Raw npm audit vẫn fail và được giữ trong CI/report. Không force fix, downgrade, suppress hoặc ẩn advisory; giữ repo/config/cert tin cậy, Metro/Compose trong phạm vi cần thiết/loopback và runtime-surface gates. Nội dung chốt privacy/ETA ngày 10/10 được ghi DEC-045, không phải phê duyệt advisory. Chủ dự án cần quyết định riêng cho M6; nếu chấp nhận, giữ review muộn nhất 02/11/2026 hoặc trước production, patch upstream/runtime exposure phải đánh giá lại ngay.

## 5. Điểm chưa xác minh / giới hạn

- Local Windows còn lỗi solver trong fixture M3 của focused suite dù cùng source full CI Linux PASS; chưa xác định nguyên nhân gốc, không tuyên bố focused local PASS.
- Chưa chạy production/TLS/public hosting, traffic/load đồng thời thực tế, GPS ngoài đường hoặc thiết bị Android/iOS vật lý; chưa phục hồi database development legacy. Không dùng test fixtures như dữ liệu nghiệp vụ canonical.
- UI đang giao/hoàn tất chưa được kiểm tra trực quan end-to-end trên database test riêng. Test API/privacy/ETA của các trạng thái đã PASS. Kiểm tra phê duyệt tự động từ chối bước khởi chạy Next tạm cổng 3006 với API_URL trỏ API test 8006, chỉ trả “blocked by policy”; không thực hiện vòng tránh, đã dừng server tạm và cleanup đúng DB/bucket UI riêng.
- Khi đọc code thấy allowlist BFF từ M5 thiếu đường đọc POD mà PodGallery gọi; chưa sửa phần M5 trong M6 theo CODEX_TOKEN_RULES §4. Public tracking không dùng/không trả POD. Cần xử lý riêng phần kết nối web POD theo contract M5 đã duyệt; không đổi permission/storage/POD gate.

## 6. Kết luận

**M6 = FAIL**: functional/build/migration/runtime và backend CI đã đạt; security gate chưa được chấp nhận riêng cho M6 nên frontend CI vẫn FAIL. Các giới hạn/điểm chưa xác minh ở §5 được giữ rõ trong báo cáo. Không tự kết luận PASS WITH ACCEPTED RISK theo DEC M5, không merge PR #5, không chuyển M7.
