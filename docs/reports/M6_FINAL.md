# M6 FINAL — Customer tracking / ETA

Cập nhật 14/10/2026. **M6 = PASS WITH ACCEPTED RISK theo DEC-046.** Accepted risk đã được duyệt theo DEC-046; không merge Draft PR #5, không chuyển M7.

## 1. Phần đã triển khai

- Áp dụng DEC-042/043/044/045: token 256 bit chỉ hash, đúng attempt/stop/xe; ADMIN/DISPATCHER cấp nhiều link, thu hồi từng link idempotently/audit. Nhân viên gửi Zalo thủ công.
- Customer tracking chỉ DTO cần thiết của đúng đơn; không đơn/khách/xe khác, GPS history, toàn tuyến, dữ liệu nội bộ hoặc POD. DELIVERED hết hạn đúng +1h; trong giờ này chỉ hoàn tất/thời điểm giao, không GPS/ETA cũ hoặc tính ETA mới.
- ETA từ GPS fresh + OSRM self-host + remaining stops/service time của tuyến đã duyệt. Kiểm tra current stop/sequence/tọa độ/giờ hẹn và provider trước cache; dữ liệu không tin cậy/GPS stale/OSRM lỗi trả UNKNOWN. Nhiều chuyến ACTIVE cùng xe thì ẩn GPS/ETA.
- BFF anonymous không chuyển auth nội bộ; Redis rate limits fail closed; no-store/no-referrer/noindex và không log raw token.
- Regression Web POD M5 đã sửa theo chỉ thị: BFF nội bộ chuyển tiếp đúng hai GET `deliveries/{id}/pod/photos` và `deliveries/{id}/pod/photos/{photo}/url`. Không mở write/public POD, không đổi backend permission/storage/signed URL policy/DELIVERED gate.

## 2. File / migration / API chính

Source cuối `a04d78401152c822192bd6e241ccba563ecb1ae8`, branch `codex/m6-customer-tracking-eta`, base M5 `a6438c9`; [Draft PR #5](https://github.com/phamdanghung/delivery-tracking/pull/5).

`apps/api/app/tracking*.py`, hook `deliveries.event`, migration `0008_m6_tracking.py`; public page/BFF, delivery link component; M6 contract snapshot/ENV/Compose/CI. Regression: internal BFF route, `apps/admin-web/tests/pod-bff.test.mjs`, npm test wiring. DEC-046 bổ sung accepted risk, không sửa DEC cũ.

API mới: POST tracking-links, POST tracking-links/{identifier}/revoke, GET public/tracking/{token}. Migration additive 0008; 0001–0007, M1–M5 contract và solver objectives giữ nguyên. Expo/React Native/dependency lockfiles không đổi.

## 3. Test / build / Docker / CI

| Kiểm tra | Kết quả và bằng chứng |
|---|---|
| POD/BFF regression | **1 PASS**: chạy handler thật với transport fixture, đúng auth/no-store, giữ 401/403, chặn write/path ngoài phạm vi. Test được chạy trong npm test/CI; backend POD/RBAC/storage thật được full CI kiểm tra |
| Local M6 thật | **14 PASS** ngày 14/10, real PostGIS/Redis/OSRM/MinIO, không diagnostic wrapper/skip/nới threshold (`artifacts/m6-oct14-focused-tests.log`); bằng chứng ngày 10/10 cũng 14 PASS |
| Lint/typecheck/web build | PASS local và CI (`m6-pod-web-build.log`); shared 7 +BFF 1 +mobile 10 tests PASS |
| CI đúng source cuối | [Run 38053386727](https://github.com/phamdanghung/delivery-tracking/actions/runs/38053386727): **backend PASS — 125 tests**, migration downgrade base → upgrade head → **40 integration PASS**; frontend ci/lint/types/tests/web/native exports/runtime gates PASS; raw npm audit FAIL được DEC-046 bao phủ. Đã đọc status và log hai job thật |
| Security surface | Web/native gates không chứa advisory packages; raw audit vẫn 21 high findings từ hai advisory, không ẩn/suppress |
| Canonical runtime | fleet-delivery-dev, head 0008, bootstrap ADMIN duy nhất và business/tracking tables rỗng; PostgreSQL/PostGIS/Redis/MinIO/Traccar/OSRM/API/admin-web đều healthy sau rebuild/restart; live/ready/MinIO private-versioning PASS. POD GET qua BFF thật chuyển tới backend (404 cho ID không tồn tại), không session 401; không tạo đơn/POD giả (`m6-oct14-pod-bff-stable.log`, `m6-oct14-stack-health.log`, `m6-oct14-canonical-verification.log`). Legacy volumes/runtime/data disk giữ nguyên |

Logs/artifacts được ignore, không commit credentials. Native exports thực tế được xác minh trong CI; không coi local test thay CI remote.

## 4. Accepted risk

**DEC-046**: braces GHSA-vfj7-8cjw-p6xm và node-forge GHSA-86w9-cpqp-85rv được chủ dự án chấp nhận tạm thời **chỉ M6 development/local/CI**. Không production, không coi đã vá. Giữ raw audit/runtime gates, repo/config/cert tin cậy và Metro/Compose phạm vi cần thiết/loopback; không force fix/downgrade/suppress. Review muộn nhất **02/11/2026 hoặc trước production**; patch upstream/runtime exposure phải đánh giá lại ngay. Raw CI frontend status vẫn FAIL tại audit, không được báo toàn workflow xanh.

## 5. Điều tra và giới hạn

- **Solver discrepancy đã có native trace**: UNKNOWN tại phase 1 budget 1s, native wall 2.110s, elapsed 7.302s, deterministic time/branches bằng 0 — hết wall-clock budget trước search trên Windows đang paging, không phải INFEASIBLE/MODEL_INVALID hoặc regression objectives. Same input/core cho OPTIMAL trên Windows/Linux; local original 14 test và full CI đều PASS. Guard NoRoute/422 vẫn giữ, không skip/nới budget/threshold/đổi fixture hoặc contract. Chi tiết [M6_SOLVER_DISCREPANCY.md](M6_SOLVER_DISCREPANCY.md).
- Cold startup trên host ít RAM từng làm OSRM health chậm và BFF login 503/read timeout. Sau khi stack ổn định, BFF/health/canonical verification PASS; lỗi đầu không bị xóa khỏi artifacts. Đây không phải bằng chứng performance production; không tự fallback/giả ETA hoặc che lỗi.
- UI đang giao/hoàn tất chưa xác minh trực quan end-to-end: thao tác Next tạm 3006 nối API test 8006 trước đó bị automatic approval review từ chối với “blocked by policy”; không bypass. API privacy/ETA/states đã PASS; expired page/mobile 390px smoke đã đạt.
- Chưa production/TLS/load thật, GPS ngoài đường/thiết bị vật lý hoặc phục hồi legacy DB. Không seed nghiệp vụ giả vào canonical; legacy containers/volumes/runtime/data disk giữ PRESERVED, không reset/prune/xóa/migrate.

## 6. Kết luận

**M6 = PASS WITH ACCEPTED RISK theo DEC-046**. POD/BFF regression đã sửa và có regression test/CI/runtime proof; solver discrepancy có native trace chứng minh budget/environment, không đổi nghiệp vụ/contract. Local M6 14 PASS, required source CI checks PASS ngoài raw audit được quyết định riêng M6 bao phủ; canonical fleet-delivery-dev healthy/head 0008, legacy bảo toàn. Các giới hạn §5 vẫn được ghi rõ; không áp dụng production. Không merge PR #5, không chuyển M7.
