# M3 FINAL

Ngày kiểm tra: 06/10/2026; cập nhật quyết định: 07/10/2026. Branch `codex/m3-route-optimization`, base M2 merge `206214f06120c5bcf797356a16edf30aceb21594`. Source `0da996e1d4ef41f1a2161318fde2d2d80b49e69d`. **M3 PASS WITH ACCEPTED RISK theo DEC-033; kiểm tra kỹ thuật/CI PASS.**

## 1. Phần đã triển khai

- DEC-030–032 được thêm mới trong PROJECT_DECISIONS; không sửa DEC cũ. Áp dụng ROUT-02, AT-04/12, WEB-07 và M3_SCOPE.
- OR-Tools giữ thứ tự số điểm vi phạm hẹn → km → thời gian; không bỏ stop, không đổi xe/chuyến đã chọn. Multi-stop và kiểm tra ba xe riêng, không giới hạn cứng fleet bằng ba. Overload warning vẫn cho duyệt.
- FIXED_TIME/config ±15 phút, service/config 10 phút và override theo stop. TIME_WINDOW/BEFORE_DEADLINE chính xác. Điều phối nhập/xác nhận departure; không tự lưu giờ gợi ý.
- OSRM self-host table/route, matrix đường thật và geometry/detail. Không geocoding/Google/gửi địa chỉ ra ngoài/fallback. Provider chỉ dùng local/private, không proxy/redirect.
- Lưu snapshot input/config/dataset và kết quả chẩn đoán có mức vi phạm; 422 vẫn commit kết quả. Duyệt chặn hard violation, input/config/dataset cũ, stop đã hủy, xe/tài xế inactive, plan không mới nhất. Không manual override.
- Duyệt hợp lệ chuyển DRAFT → PLANNED, đơn/stop PLANNED → ASSIGNED; audit và status events. Không thêm trạng thái/nghiệp vụ M4.
- WEB-07 map/panel 65/35, stop đánh số, km/thời gian/ETA, cảnh báo và duyệt; mobile xếp dọc. Form lấy giá trị xác nhận khi submit, giữ dữ liệu khi lỗi/retry; chặn thay đổi chưa tối ưu lại.

## 2. File/migration/API chính

Backend `app/route_optimizer.py`, `route_policy.py`, `routing_provider.py`, `routes.py`, `route_schemas.py`, config/main; migration **0004**; uv/requirements locks thêm OR-Tools 9.15.6755 và năm dependency transitive, không đổi Expo/React Native/npm lock.

API additive `/api/v1/routing/config`, `/api/v1/trips/{id}/optimize`, `optimization`, `approve`; snapshot `openapi/m3.openapi.json`. Baseline SQL/OpenAPI, snapshots M1/M2 giữ nguyên và có compatibility tests. M2 chỉ đổi câu báo lỗi start để phản ánh M3.

Web `dispatch/optimization.tsx`, route `/trips/[id]/optimize`, BFF whitelist, liên kết chi tiết chuyến và marker numbered; reuse auth/session/sidebar/map/tokens. Compose thêm OSRM loopback/read-only; scripts prepare/verify OSRM, dev/verify/database harness; CI dựng graph thật từ `infra/osrm/fixtures/Saigon.osm.pbf`.

Extract public OSM/BBBike 15,264,796 bytes, SHA256 `305729efc04180b6a151ba3d61f6bb5c91b05ed044eed734b30f3625f806119b`; nguồn/ODbL trong README cạnh fixture. CI run đầu 37461848874 lỗi tải BBBike timeout trước pytest; source 0da996e thay lượt download CI bằng chính bytes đường thật đã kiểm checksum. Không thay bằng mock.

## 3. Kiểm tra và bằng chứng

| Kiểm tra | Kết quả |
|---|---|
| Backend local full | **74 PASS**, không skip; `artifacts/m3-full-database.log`, `m3-api-tests.xml` |
| Migration/PostGIS | Dev head **0004**, PostGIS thật; isolated upgrade/downgrade/upgrade PASS, integration rerun **18 PASS** |
| Core OR-Tools | 9 test giữ nguyên, PASS trong regression; đúng hẹn trước km, km trước thời gian, mandatory/unreachable |
| M3 real integration | 5 PASS: ba xe/multi-stop, approval/overload/roles/events/audit, infeasible persist/block/reoptimize, stale/config/latest/cancel, provider/departure/service; ca 30 điểm API <5s |
| Lint/typecheck | Python Ruff/format/mypy PASS; web/mobile lint/typecheck PASS; shared **7 PASS** |
| Web | Build PASS; **19** server traces, 0 references braces/node-forge; `m3-web-runtime-surface.json` |
| Browser QA | Real isolated PostGIS + local OSRM: empty/confirmation/optimize/approve, hard violations, service override, dirty form/retry retained, real OSRM outage/error/no fallback; screenshots `m3-ui-approved.png`, `m3-ui-time-violation.png`, `m3-ui-mobile.png`, `m3-ui-osrm-outage.png` |
| Responsive | Viewport mobile: client/scroll width đều 375px, không tràn ngang; reset về mặc định |
| Docker | Engine 29.7.2; api/admin-web/postgres/redis/minio/traccar/osrm **healthy**, minio-init exit **0**; `m3-containers.json` |
| Health | API live/ready, PostGIS head, Redis, MinIO signed read/write/versioning + anonymous 403, Traccar PASS; OSRM matrix/road geometry **85 points** PASS; `m3-stack-health.json`, `m3-osrm-health.json` |
| npm ci/mobile export | Frontend remote CI source 0da996e PASS; clean install, Android/iOS export, runtime maps 578/580 sources sạch; chưa phải APK/IPA |

Ngân sách solver default 3s qua config để dành thời gian cho routing/DB; nếu chưa chứng minh tối ưu toàn cục, response/UI ghi cảnh báo và proven objectives. Hard time approval không được bỏ qua khi solver hết ngân sách. Mục tiêu <5s được kiểm ở fixture 30 điểm/1 xe; đây không phải nghiệm thu performance production mọi vùng/quy mô.

## 4. CI remote

Source `0da996e1d4ef41f1a2161318fde2d2d80b49e69d`, [run 37462411127](https://github.com/phamdanghung/delivery-tracking/actions/runs/37462411127): **completed/success**, frontend và backend **PASS**. Đã tải/đọc log thực tế `artifacts/m3-ci-frontend.log`, `m3-ci-backend.log`; metadata tại `m3-ci-status.json` khớp source SHA.

Frontend: clean npm ci 765 packages, audit **19 high** hiển thị; lint/typecheck, shared **7 PASS**, web build/**19** traces sạch, Android/iOS export và **578/580** sources sạch. Backend: uv frozen/lint/format/mypy, graph OSRM dựng thật từ PBF đã kiểm checksum và table/route PASS, PostGIS/Traccar thật, **74 PASS** (21.11s), migration downgrade/upgrade, **18 integration PASS** (17.22s). Không dùng local tests thay bằng chứng remote. Commit báo cáo sau source không thay ứng dụng/lock/migration/CI đã xác minh; không tự chạy lại checks chỉ vì tài liệu đổi.

CI source M3 đã được xác nhận vẫn PASS. Commit tài liệu `f6507914bd01791f3a4434190ac0d6b0ebcc921a`, [run 37462918774](https://github.com/phamdanghung/delivery-tracking/actions/runs/37462918774), cũng **completed/success**, cả frontend/backend PASS trên cùng source. Các artifact log/metadata hiện lưu run này. Cập nhật DEC-033 và kết luận chỉ đổi tài liệu, không đổi code/dependency/migration/CI; bằng chứng kỹ thuật vẫn áp dụng theo CODEX_TOKEN_RULES mục 15.

Draft [PR #2](https://github.com/phamdanghung/delivery-tracking/pull/2), base `codex/m0-foundation`. Chưa merge; không tự chuyển M4.

## 5. Security và quyết định chấp nhận rủi ro có điều kiện

Audit M3: **19 high, 0 critical**, hai advisory gốc **braces GHSA-vfj7-8cjw-p6xm** và **node-forge GHSA-86w9-cpqp-85rv**, chưa vá. `m3-npm-audit.json` giữ toàn bộ findings; `m3-dependency-security.json` phân loại và liệt kê 20 paths braces, 2 node-forge, 10 uuid. Không đổi npm dependency hoặc che/ignore findings.

Đã đối chiếu lại ngày 06/10/2026: GitHub Advisory vẫn ghi không có patched version cho [braces](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) (stack-exhaustion DoS, <=3.0.3) và [node-forge](https://github.com/advisories/GHSA-86w9-cpqp-85rv) (RSA signature verification, <=1.4.0). Không có override sang bản upstream đã vá tại thời điểm rà soát.

Findings lan truyền qua Expo/RN; hai package gốc đi qua Metro/glob/build tooling và Expo certificate tooling. Expo/RN là dependency runtime trực tiếp nhưng điều đó không chứng minh braces/node-forge được bundle vào runtime. Web traces và Android/iOS source maps hiện không có hai package; rủi ro thực tế vẫn tồn tại với repo/config/cert không tin cậy trong dev/build/CI. Không coi audit đã sạch hay production đã an toàn.

**DEC-033, ngày 07/10/2026:** chủ dự án phê duyệt chấp nhận tạm thời cả hai advisory riêng cho **M3 development/local/CI hiện tại**, không production hoặc milestone khác. Giữ nguyên DEC-023/024/029. Không xem advisory là đã vá hoặc bỏ qua kiểm soát bảo mật khác.

Giữ repo/config/cert đáng tin cậy; Metro/Compose chỉ expose trong phạm vi cần thiết/loopback; không `npm audit fix --force`, không downgrade Expo/React Native chỉ để audit về 0, không suppress/ẩn advisory; tiếp tục npm audit và runtime-surface gates trong CI/report. Review muộn nhất **02/11/2026** hoặc trước production, mốc sớm hơn. Nếu upstream có bản vá sớm hơn, ưu tiên nâng cấp và chạy lại đầy đủ npm ci, build, Android/iOS export, test, Docker/stack/health và CI remote. Nếu advisory đi vào runtime attack surface thực tế ở milestone sau, dừng phần liên quan và đánh giá lại ngay.

## 6. Điểm chưa xác minh và kết luận

Hai advisory chưa được vá, được chấp nhận tạm thời đúng phạm vi DEC-033. Production, APK/IPA/GPS vật lý, vùng đường ngoài extract Saigon và milestones sau ngoài phạm vi M3; không được suy từ các fixture local/CI. Database QA riêng đã được hủy bằng harness sau kiểm tra; database vận hành không được reset/downgrade.

**M3: PASS WITH ACCEPTED RISK theo DEC-033, đủ điều kiện đóng trong phạm vi M3 development/local/CI.** Source/test/migration/build/export/Docker/health/CI đã PASS; hai advisory còn mở được chủ dự án chấp nhận tạm thời có điều kiện. Không merge PR #2 khi chưa có chỉ thị, không chuyển M4.
