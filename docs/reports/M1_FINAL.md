# M1 FINAL — Users / Fleet / GPS / Traccar

Ngày nghiệm thu: 05/10/2026 (Asia/Bangkok). Nhánh `codex/m1-auth-fleet-gps`. M1 **PASS WITH ACCEPTED RISK** theo DEC-024; M0 giữ nguyên trạng thái theo DEC-023. Không làm lại M0 hoặc chuyển M2.

## 1. Phạm vi đã triển khai

- Auth: Argon2id, access JWT ngắn hạn, refresh rotation/replay revocation, logout, tài khoản đang hoạt động và RBAC server-side.
- ADMIN quản trị user/xe/device mapping/profile; DISPATCHER đọc fleet/GPS/history/profile; DRIVER chỉ đọc tài khoản của mình trong M1. Không tự cấp thêm quyền quản trị cho điều phối.
- Vehicle CRUD, unique biển số/device, kiểm tra device có thật trong Traccar. Không hard-code số xe.
- DriverProfile liên kết User; xe liên kết tài xế qua Trip theo schema/nghiệp vụ đã khóa. M1 chỉ đọc liên kết Trip hiện có, không tạo workflow phân chuyến hoặc quan hệ xe cố định mới.
- Live GPS, ACC/engine state, freshness, lịch sử/playback, điểm dừng/thời gian dừng, quãng đường theo Traccar report, audit hành động quản trị.
- Giữ nguyên các quyết định mới: tài xế chỉ đề xuất giao lại, điều phối xác nhận; safety NEW/SEEN/RESOLVED tách biệt. Hai workflow này chưa triển khai ở M1. Đề xuất bổ sung schema safety được ghi tại `docs/requirements/M1_SCOPE.md` cho M7.

Đã đọc lại START_HERE V1.1, nghiệp vụ V1.1 khóa, Technical Pack V1.0, toàn bộ UX/UI V1.0 và PROJECT_DECISIONS; phạm vi/contract bổ sung được ghi trước code. Không triển khai delivery workflow, optimization, POD, customer tracking, fuel/maintenance hoặc remote immobilization.

## 2. Kiến trúc và luồng dữ liệu GPS thực tế

Feed OsmAnd **mô phỏng có kiểm soát** → Traccar 6.10 Docker thật (HTTP 5055) → REST `/api/positions`, history/report và WebSocket `/api/socket` → adapter trong FastAPI hiện có → snapshot/state transitions ở PostGIS → API có RBAC → Next.js BFF cùng origin/cookie HttpOnly → Leaflet.

REST polling 5 giây làm fallback; WebSocket có reconnect. Hai đường ingest cùng kiểm tra mapping, deduplicate position và từ chối bản tin cũ hơn. GPS thô/lịch sử vẫn thuộc Traccar; backend không sao chép toàn bộ GPS. Tách GPS fix time, Traccar server receive time và backend receive time.

Không thêm service hoặc đổi modular monolith. Secret lấy từ ENV, không trả Traccar credentials/token cho frontend. Các cổng local chỉ bind loopback; Metro giữ local. Basemap OSM có attribution; chưa phê duyệt provider/deployment production.

## 3. Database/migration thay đổi

Migration Alembic `0002_m1_foundation` thêm:

| Bảng | Mục đích |
|---|---|
| auth_sessions | Refresh hash, family, expiry/revocation; không lưu refresh plaintext |
| gps_snapshots | Vị trí cuối theo vehicle, device/position, telemetry/ACC/timestamps |
| vehicle_state_events | Chuyển trạng thái động cơ, một interval mở mỗi xe |

Baseline `0001` và SQL cung cấp giữ nguyên. Database dev đã migrate thật tới `0002`, PostGIS 3.5; inspector thấy 58 bảng gồm bảng extension, không phải 58 bảng nghiệp vụ. Database test riêng đã upgrade → full suite → downgrade base → upgrade → chạy lại integration; sau đó xóa đúng database UUID do lần kiểm tra tạo. Không downgrade/reset database vận hành.

## 4. API đã triển khai

| Endpoint dưới `/api/v1` | Quyền |
|---|---|
| POST auth/login, auth/refresh | Credentials hoặc refresh token hợp lệ |
| POST auth/logout; GET auth/me | Phiên hợp lệ, thông tin chính user |
| GET/POST users; PATCH users/{user_id} | ADMIN |
| GET vehicles | ADMIN/DISPATCHER |
| POST vehicles; PUT/DELETE vehicles/{vehicle_id} | ADMIN |
| GET drivers | ADMIN/DISPATCHER; liên kết xe chỉ đọc qua Trip |
| PUT drivers/{driver_id} | ADMIN; giữ User của profile đã tạo |
| GET gps/devices | ADMIN |
| GET vehicles/{vehicle_id}/live, /history, /odometer | ADMIN/DISPATCHER |

History/report yêu cầu timezone, khoảng hợp lệ và tối đa 31 ngày mỗi truy vấn. API trả 401/403/404/409/422/503 theo tình huống, không trả SQL/credentials. Không vô hiệu hóa ADMIN hoạt động cuối; thay role/password/active thu hồi phiên. User/vehicle/profile mutations có audit actor/time/before/after/request ID, loại password/token khỏi audit.

`openapi/m1.openapi.json` sinh từ source, có schemas/auth/security/telemetry/history/stops/driver/assignment/report. Test so sánh trực tiếp với FastAPI. `openapi/openapi.yaml` nghiệp vụ gốc giữ nguyên byte; các bổ sung M1 có giải thích trong M1_SCOPE, không đổi contract M2+.

## 5. Mapping Traccar device ↔ vehicle

Integration suite tạo **3 device thật và 3 vehicle** trong môi trường test, đọc REST, nhận bản tin trên WebSocket thật, kiểm tra live/history/report và cleanup đúng các ID đã tạo.

Kiểm tra stack/UI riêng feed cả 3 xe mô phỏng và xác nhận NORMAL/MOVING, STALE/IDLING, LOST/PARKED. UI chọn device từ Traccar thật; thử gán device đã liên kết trả 409, form giữ thông báo lỗi qua các lần polling. Đổi mapping xóa snapshot của device cũ và kết thúc interval cũ để không hiển thị vị trí sai xe. Unique constraints xử lý cạnh tranh ở database.

Đã dọn 3 fixture UI vehicle/device. Hai user mô phỏng đã vô hiệu hóa/thu hồi phiên; giữ audit/history tài khoản theo schema. Không xóa dữ liệu khác hoặc volume. Đây **không phải nghiệm thu GPS vật lý**.

## 6. Quy tắc NORMAL/STALE/LOST

| Tuổi dữ liệu | Backend/API/Web |
|---|---|
| 0 đến đúng 30 giây | NORMAL — Bình thường |
| >30 đến đúng 120 giây | STALE — Dữ liệu chậm |
| >120 giây | LOST — Mất tín hiệu GPS |

Tuổi dữ liệu lấy giá trị lớn hơn giữa tuổi GPS fix và tuổi Traccar server receive; fix cũ vừa được nhận không trở thành live. Null/invalid/future timestamp không được giả là NORMAL. UI cập nhật tuổi cache mỗi giây, gắn nhãn **Vị trí cuối ghi nhận** và động cơ **lần cuối** với dữ liệu cũ.

Speed đổi knots → km/h. Speed >0 + ACC=true → MOVING; speed=0 + ACC=true → IDLING; speed=0 + ACC=false → PARKED. ACC thiếu/GPS invalid hoặc tổ hợp chưa đủ căn cứ → UNKNOWN. Không tự đặt ngưỡng tốc độ khác 0. History không nối polyline hoặc cộng thời gian dừng qua gap >120 giây/invalid GPS.

## 7. Kết quả web UI

WEB-01/03/09/14 và quản trị xe cơ bản đã xác minh trên bản build Docker thật: login/show password/busy/error; sidebar/topbar cố định; list/search/filter; map và popup biển số/tài xế/speed/course/ACC/engine/fix/server time/coordinates; badges; vehicle form; users/role presets; history/playback/stops/gaps/km.

Đã xác minh loading, empty filter và empty fleet, validation/network error, permission, GPS cũ và phiên hết hiệu lực. DRIVER bị chặn fleet; DISPATCHER không có nút quản trị; thu hồi phiên thật đưa người dùng về login. Request foreign/missing Origin bị chặn, login loopback hợp lệ, cookie HttpOnly/SameSite Strict, token không có trong login response browser, concurrent refresh/logout đạt.

1440×900, 768×1024, 360×800 không tràn ngang; popup sau chỉnh có chiều rộng khoảng 241 px thay vì cột chữ quá hẹp. Popup không bị dựng lại mỗi nhịp đồng hồ. Playback đến bản tin cuối đạt; dữ liệu dừng mô phỏng có interval quan sát 51 giây, hiển thị rõ gap và không tạo thời gian dừng qua đoạn thiếu dữ liệu.

Ngắt container Traccar thật: web chuyển LOST/cảnh báo, giữ 3 marker vị trí cuối; sau restart healthy kết nối hồi phục. Bằng chứng local ở `artifacts/m1-ui-*.png/json`; không commit credentials/artifacts.

## 8. Kết quả test

| Kiểm tra | Kết quả |
|---|---|
| Backend full suite, PostGIS/Traccar thật | **44 PASS, 0 fail, 0 skip** |
| Integration sau downgrade/upgrade lại | **3 PASS**, lặp lại trong 44 test, không cộng thành test mới |
| Node/shared/UI freshness/Origin/baseline | **5 PASS, 0 fail, 0 skip** |
| Ruff check/format; mypy | PASS |
| npm ci với npm 12.2.0 | PASS clean install |
| Web production build và Docker API/web image | PASS |
| Expo SDK 57 Android/iOS export | PASS; không downgrade Expo/React Native |
| Real stack/BFF/Traccar outage/browser checks | PASS |

Tổng suite duy nhất: **49 test PASS**. Unit tests có stub để kiểm tra nhánh lỗi; bằng chứng database/Traccar/stack/migration chính dùng dịch vụ thật, không lấy stub thay thế integration. Có warnings không nghiêm trọng của Starlette/httpx, Alembic và npm/Node; không suppress.

Audit kiểm tra lại ngày 05/10: **19 high, 0 critical**, do 2 advisory root, không phải 19 advisory độc lập. Latest registry vẫn braces 3.0.3 và node-forge 1.4.0. Không dùng audit fix --force, downgrade Expo hoặc hide/ignore findings.

| Root advisory | Đường tiêu biểu / phân loại thực tế |
|---|---|
| braces GHSA-vfj7-8cjw-p6xm | admin-web → eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces; build/lint tooling transitive |
| node-forge GHSA-86w9-cpqp-85rv | driver-mobile → expo → @expo/cli → node-forge; và @expo/code-signing-certificates → node-forge; build/dev/certificate tooling transitive |

19 nodes bị npm đánh dấu gồm Expo/RN runtime parents và Metro/CLI/lint parents; không lấy nhãn npm prod/dev làm bằng chứng runtime. Kiểm tra **11 Next server traces** của Docker build mới không có braces/node-forge; Android/iOS source maps lần lượt 578/580 sources không có advisory package source. Expo runtime loader được kiểm tra riêng theo gate M0; không đồng nhất loader với certificate/CLI tooling. Docker dev image vẫn cài tooling, chưa được tuyên bố production-safe.

UUID của xcode giữ override 11.1.1 đã xử lý tại M0. M1 thêm Leaflet/@types và PyJWT/Argon2 dependencies; không xuất hiện advisory npm mới. CI giữ audit trong npm ci/log và thêm gate web/mobile: advisory root đi vào bundle/traces sẽ FAIL. Chủ dự án đã phê duyệt exception riêng cho M1 tại DEC-024; hai advisory **chưa được vá**, chỉ được chấp nhận tạm thời trong phạm vi đã duyệt.

## 9. Docker/stack/health

Docker Engine 29.7.2 hoạt động. Sáu service dài hạn postgres, redis, minio, traccar, api, admin-web đều healthy; minio-init Exited(0). Database dev `0002`; API liveness/readiness 200 với database/redis/storage/traccar=true; web 200; Traccar authenticated REST/WebSocket đạt. Redis PONG; MinIO private/versioning Enabled, signed write/read PASS, anonymous read 403; xóa đúng object version kiểm thử.

Khi Traccar thật dừng, readiness/live GPS trả 503 đúng; restart hồi phục healthy. Giữ bind loopback, Postgres host 55433, không reset Engine/volumes hoặc tác động service dự án khác. Log cuối: `artifacts/m1-stack-health.json`, `m1-real-outage.json`, `m1-docker-web-final.log`, `m1-database-tests.log`.

## 10. CI remote

Repository: https://github.com/phamdanghung/delivery-tracking.git. Workflow `M1 auth fleet GPS`, hai job frontend/backend, services PostGIS và Traccar thật, test/export/upgrade-downgrade-upgrade/integration rerun và runtime-surface gates.

CI checkpoint của source `640ef3cb293f51f628bee2245ed8d69382c81755`: **PASS**, [run 37323566867](https://github.com/phamdanghung/delivery-tracking/actions/runs/37323566867), cả frontend và backend completed/success. Đã tải và đọc log thực tế: backend 44 PASS, migration round-trip và integration rerun 3 PASS; frontend 5 PASS, clean install/build/export thành công, 11 server traces và 578/580 mobile sources đạt runtime gates. Audit 19 high vẫn hiện trong log. Local tests không thay bằng chứng CI. Commit bàn giao báo cáo sau checkpoint này chỉ thay tài liệu.

CI của commit bàn giao `e8438d92a9c0aea309372ddb2019ce7f309ae4fa` cũng **PASS** cả frontend/backend: [run 37324651082](https://github.com/phamdanghung/delivery-tracking/actions/runs/37324651082). Cập nhật DEC-024/kết luận chỉ thay tài liệu, giữ nguyên source/dependency/workflow đã xác minh; không cần chạy lại kiểm tra tốn tài nguyên chỉ vì cập nhật tài liệu.

## 11. Các file chính đã thay đổi

- API: `app/auth.py`, `database.py`, `fleet.py`, `gps.py`, `traccar.py`, `schemas.py`, `main.py`, `health.py`, `config.py` dưới apps/api; migration 0002 và test contract/GPS/API/real Traccar.
- Web: `app/fleet/{console,map,gps-state}.tsx/ts`, các page live/vehicles/history/users/login, BFF `app/api/internal`, CSS/layout; Leaflet dependency và npm lock.
- API dependency/locks: pyproject.toml, uv.lock, requirements.lock. Không sửa SDK/RN hoặc source driver-mobile.
- ENV/Compose; bootstrap local/CI, exporter OpenAPI, database/stack/UI verification, web surface gate, dev/verify PowerShell và CI workflow.
- `openapi/m1.openapi.json`, README, M1_SCOPE/M1_TRACEABILITY/M1_FINAL; đưa PROJECT_DECISIONS nguồn người dùng cung cấp vào Git, không thay các quyết định đã khóa.

## 12. Các vấn đề chưa xác minh

- Chưa có GPS vật lý: chưa nghiệm thu protocol thiết bị thực, tín hiệu ACC/dây đấu, GNSS ngoài hiện trường, GPS/SIM mất mạng hoặc độ chính xác quãng đường thực.
- Chưa build native APK/IPA/chạy điện thoại; M1 chỉ giữ skeleton và export bundle M0.
- Chưa nghiệm thu production: TLS/hosting/provider map/credentials/backup/security hardening và rủi ro advisory production phải review riêng.
- Hai advisory còn tồn tại, được chấp nhận có điều kiện theo DEC-024; không coi là đã vá hoặc được phê duyệt production. CI source đã xác minh thành công tại mục 10.

Các giới hạn hardware/native/production đã được tách khỏi bằng chứng M1 local/simulator theo chỉ thị; không tuyên bố đã nghiệm thu chúng.

## 13. Các điểm cần chủ dự án quyết định

**Đã chốt:** ngày 05/10/2026, chủ dự án phê duyệt riêng M1 development/local/CI tại **DEC-024** cho braces GHSA-vfj7-8cjw-p6xm và node-forge GHSA-86w9-cpqp-85rv. DEC-023 của M0 giữ nguyên. Không còn quyết định advisory chặn đóng M1; không áp dụng production hoặc tự mở rộng sang milestone khác.

Điều kiện bắt buộc theo DEC-024: repo/config/cert đáng tin cậy; Metro loopback; Docker không expose thừa; không force/downgrade Expo/React Native/suppress; giữ audit và runtime-surface gates trong CI/report, không miễn trừ kiểm soát khác. Review trước **03/11/2026 (muộn nhất 02/11/2026)** hoặc trước production, mốc sớm hơn. Có patch sớm: ưu tiên nâng và chạy lại npm ci, build, Android/iOS export, test, Docker/stack/health và CI remote. Advisory vào runtime thực tế ở milestone sau: dừng phần liên quan và đánh giá lại.

Sau review M1, cần chỉ thị riêng trước M2. Chọn/đấu thiết bị GPS và basemap production là quyết định triển khai sau, không được suy rộng từ simulator/local.

## 14. Kết luận M1: PASS WITH ACCEPTED RISK

**PASS WITH ACCEPTED RISK** theo phê duyệt rõ của chủ dự án tại DEC-024. Các hạng mục kỹ thuật local/simulator và hai job CI remote đã đạt; hai advisory vẫn tồn tại và chịu các điều kiện/theo dõi trên. Không có thay đổi nghiệp vụ hoặc kiến trúc ngoài phạm vi M1 được phát hiện sau đối chiếu/kiểm thử.

M1 đã đủ điều kiện đóng trong phạm vi development/local/CI đã duyệt. Không chuyển M2; chờ chỉ thị riêng của chủ dự án. Không tuyên bố nghiệm thu GPS vật lý/native app/production.
