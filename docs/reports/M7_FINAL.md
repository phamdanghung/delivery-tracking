# M7 FINAL — Fuel / Expenses / Maintenance / Safety

Cập nhật 15/10/2026. **M7 = FAIL — chờ quyết định accepted risk riêng cho M7.** Chưa merge PR #6, không chuyển M8. DEC-046 chỉ bao phủ M6.

## 1. Phần đã triển khai

- DEC-047: fuel entries; kỳ FROM/TO được xác nhận; tổng hợp nhiều lần đổ, telemetry Traccar thực tính một lần và chia theo hiệu lực profile. Giữ signed variance, cảnh báo ABS >15%; thiếu dữ liệu không giả variance. FINAL không overlap; mỗi lần tính lại có version/audit bất biến.
- DEC-048: cấu hình/ngoại lệ safety theo xe, hữu hạn và có lý do; GPS fresh + ACC/activity; incidents chống trùng REST/socket. Giữ NEW → SEEN → RESOLVED, resolve bắt buộc lý do. Không bật harsh braking/out-of-area khi chưa có threshold/contract được duyệt; không remote immobilization.
- DEC-049: chi phí đúng RBAC; DRIVER chỉ chi phí của mình, outbox/conflict/idempotency M4 và receipt private tùy chọn. Bảo dưỡng riêng từng xe theo km/ngày, điều kiện đến trước; lead tường minh, nguồn odometer rõ, không giả mốc. Event append-only; giấy tờ/nhắc hết hạn có audit.
- WEB-10/11/12 reuse shell/tokens; DRV-07/08 reuse tab Chi phí/outbox. Receipt camera/album dùng kiểm tra ảnh/EXIF/private versioned storage M5; bind đúng actor/command/trip hoặc vehicle/kind. Không mở POD/customer tracking, không triển khai M8.

## 2. File / migration / API chính

Base M6 merge `b1e30f1cb3f446f38730261c39e3d8961bf4271a`; source cuối `85edc2125d1dce2744ea6da7d8f66ce5258f4236`, branch `codex/m7-fuel-maintenance-alerts`; [Draft PR #6](https://github.com/phamdanghung/delivery-tracking/pull/6).

- `apps/api/app/fuel*.py`, `operations_policy.py`, `expenses.py`, `expense_receipts.py`, `vehicle_receipts.py`, `maintenance*.py`, `safety*.py`; GPS hooks và additive expense action trong driver API.
- Migration `0009_m7_operations.py`; OpenAPI `openapi/m7.openapi.json`. Các nhóm fuel/profiles/entries/reconciliations, expenses/receipts, maintenance/rules/events/odometer, vehicle-documents, safety/configs/exceptions/alerts.
- `apps/admin-web/app/operations/*`, internal BFF allowlist/receipt transport; `apps/driver-mobile/src/expenses/*`, owner-scoped cache/outbox và picker recovery. Tests tương ứng; DEC-047/048/049, `M7_SCOPE.md`, CI và verification scripts.
- Không đổi migrations 0001–0008, snapshots M1–M6, solver/objectives/fixture M3, Expo SDK 57/React Native 0.86.3 hoặc dependency lockfiles. Các thay đổi contract cũ chỉ additive driver expense command/response được compatibility tests kiểm tra.

## 3. Test / build / Docker / CI

| Kiểm tra | Bằng chứng |
|---|---|
| Backend local | **186 PASS**, không skip, trên PostGIS/Redis/MinIO/OSRM/Traccar thật, DB/bucket test cô lập. `artifacts/m7-full-database-recheck.log` |
| Migration local | Upgrade canonical 0008 → 0009 PASS; trên DB test, downgrade base → upgrade head → **52 integration PASS**, cleanup chỉ DB/bucket của lượt test. Cùng log trên |
| Policy / dữ liệu thật | Trong suite có 48 policy/telemetry/maintenance tests; actual Traccar report/positions kiểm tra profile boundary, nhiều lần đổ, idle, km thực, signed variance và đúng biên ±15%. Thiết bị mô phỏng, không phải nghiệm thu GPS ngoài đường |
| RBAC / offline / receipts / audit | Own-cost privacy; restart/reconnect/lost response; cùng entity conflict nhưng entity khác tiếp tục; stable ID/no duplicate upload/event; private/versioned ảnh; maintenance reset/unknown odometer; safety episode/state/reason/audit đều PASS |
| Frontend local | Lint/typecheck PASS; shared/BFF **9 PASS**, mobile **12 PASS**; web production build PASS; Android/iOS Hermes exports PASS; web/native runtime-surface gates không có advisory package sources. `m7-npm-tests.log`, `m7-lint.log`, `m7-typecheck.log`, `m7-web-build.log`, `m7-mobile-export.log`, `m7-*-surface.log` |
| Remote CI source cuối | [Run 38753829207](https://github.com/phamdanghung/delivery-tracking/actions/runs/38753829207), head `85edc21`: backend **PASS — 186 tests + downgrade base → upgrade head → 52 integration PASS**. Đã đọc status và log thật hai job |
| Frontend CI / npm ci | Clean `npm ci`, lint/types/tests, web build, Android/iOS export và runtime gates đều PASS. **Frontend job và toàn workflow vẫn FAIL tại npm audit: 21 high findings**, không gọi workflow xanh. Local không chạy lại npm ci vì manifests/lockfiles không đổi; CI đã chạy clean install trên source cuối |
| Canonical runtime | `fleet-delivery-dev`, PostGIS 3.5.2, head **0009**. API live/ready, admin-web, Redis, MinIO private/versioning, Traccar, OSRM matrix/geometry PASS; 7 service healthy. Bootstrap ADMIN duy nhất; business/tracking/M7 tables rỗng, BFF login/list/logout PASS. API image cuối chứa cả bản sửa rollback. `m7-final-canonical-verification.log`, `m7-final-stack-health-stable.log`, `m7-osrm-health.log` |

Artifacts được ignore, không commit credentials/test tokens. Canonical migrate tiến lên; downgrade/round-trip chỉ trên DB test. Legacy `fleet-delivery` và các volume/runtime/data disk vẫn PRESERVED, không reset/prune/xóa/migrate; không coi là production data.

## 4. Điểm chưa xác minh / giới hạn

- Kiểm tra trực quan các màn hình M7 chưa hoàn tất: helper Windows từng timeout, sau đó chủ dự án dừng Computer Use bằng Escape. Không tiếp tục thao tác UI sau tín hiệu dừng. Build/BFF/API và đối chiếu source với UX vẫn được kiểm tra; không coi đó là nghiệm thu trực quan hoặc native device E2E.
- Chưa nghiệm thu thiết bị Android/iOS vật lý, telemetry ngoài đường, production/TLS/load hoặc phục hồi legacy DB.
- Trong lượt khởi động lạnh trên host Windows đang paging đã xảy ra readiness/protocol error và bài M3 30 stop trả 422. Sau ổn định, cùng source/rule/fixture và ngưỡng <5s giữ nguyên đều PASS trong full local 186 và CI. Không skip/nới ngưỡng/fallback hoặc đổi solver. Các lượt lỗi vẫn giữ trong artifacts.
- Hai lỗi test đã xử lý: xe có lịch sử safety phải giữ guard 409 (xe chưa có lịch sử vẫn 204); thứ tự audit kiểm tra theo version tường minh. CI cũng phát hiện rollback 0009 xóa cột trước unique constraint; đã sửa riêng thứ tự downgrade của migration M7 mới, không đổi upgrade/schema hoặc migration lịch sử. Round-trip CI đã PASS.

## 5. Quyết định cần chủ dự án

Hai advisory chưa vá vẫn hiện trong raw audit:

- [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
- [node-forge GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv).

21 affected-package findings xuất phát từ hai advisory gốc; phân loại/đường dependency tham chiếu [M0_DEPENDENCY_SECURITY.md](M0_DEPENDENCY_SECURITY.md). Lockfiles không đổi; web traces và Android/iOS maps hiện tại không đưa các package advisory vào runtime bundle. Tooling vẫn tồn tại trong dependency tree/image, không tuyên bố đã loại bỏ/vá. Module M7 không thêm đường sử dụng các package này từ input nghiệp vụ.

**Chưa có phê duyệt M7; không tự mở rộng DEC-046.** Nếu chủ dự án chấp nhận tạm thời, cần DEC mới chỉ M7 development/local/CI, không production/không coi đã vá; giữ raw audit/runtime gates, repo/config/cert tin cậy và Metro/Compose phạm vi cần thiết/loopback; không force fix/downgrade/suppress. Đề xuất review muộn nhất **02/11/2026 hoặc trước production**, patch upstream/runtime exposure phải đánh giá lại ngay.

## 6. Kết luận

**FAIL — còn blocker accepted risk M7 chưa được phê duyệt.** Functional tests/builds và CI backend đã PASS; raw npm audit/CI frontend vẫn FAIL được báo nguyên trạng. Chưa merge Draft PR #6; không tự chuyển M8.
