# M4 FINAL

Ngày chốt bằng chứng: **08/10/2026**. Branch `codex/m4-driver-offline-geofence`, base M3 merge `8d95b1c7c08df79f24335526c9e2763a02309e29`; source kiểm tra `97e9d449101fff7cc6968d310a2ebe2f5a65ff57`. [Draft PR #3](https://github.com/phamdanghung/delivery-tracking/pull/3), chưa merge.

## 1. Phần đã triển khai

- Driver App: chuyến/stop của chính tài xế, cam kết/ETA/lộ trình, timeline, gọi/mở chỉ đường bằng tọa độ; trạng thái cache/offline/queue/sync/lỗi rõ ràng. Áp dụng M4_SCOPE và M4_TRACEABILITY.
- SQLite cache/outbox theo owner; SecureStore token trên native. Persist trước khi báo lưu; FIFO, single-flight, retry cùng payload/id, phục hồi sau restart, sync reconnect/foreground. Cache kết quả ACK trước khi đánh dấu SYNCED; action đã SYNCED không đảo trạng thái mới từ server. Web preview dùng localStorage cho cache/queue, token chỉ trong bộ nhớ.
- Receipt transaction theo actor/client_action_id giữ lâu hơn 24 giờ; replay trả kết quả cũ, không tạo event/audit trùng. Cùng id khác payload bị từ chối; RBAC/state machine/POD gate vẫn kiểm tại server.
- Geofence từ GPS Traccar hợp lệ/fresh, khoảng cách PostGIS thật, stop kế tiếp của chuyến ACTIVE; không thay bằng GPS điện thoại. DEC-034 bổ sung mới, giữ DEC-004: sửa ARRIVED → EN_ROUTE có lý do/audit, trip ACTIVE; khóa tự ARRIVED tới GPS mới >70m, lần vào ≤50m tiếp theo mới ARRIVED. Không timeout hoặc transition ngược khác.
- Không triển khai camera/upload POD M5, Customer Tracking M6 hoặc chi phí M7. Chưa có POD hợp lệ vẫn không cho DELIVERED.

## 2. File/migration/API chính

- Backend `apps/api/app/driver.py`, `geofence.py`, tích hợp `gps.py`/`main.py`; migration **0005_m4_driver_actions**, bảng receipt và trạng thái geofence. OpenAPI additive `openapi/m4.openapi.json`; snapshots M1/M2/M3 giữ nguyên và được compatibility test.
- API `/api/v1/driver/today`, `/api/v1/driver/actions`, `/api/v1/deliveries/{id}/arrival-correction`; Web BFF/detail thêm correction theo quyền hiện có.
- Mobile `src/app`, `src/driver`, `src/offline`, tests; Expo Router theo AGENTS.md. Expo SDK **57.0.27**, React Native **0.86.3**, React **19.2.3**; không đổi major stack.
- `package.json`/lock, CI, Web Dockerfile: npm **12.2.0**, upstream decoder **0.5.0** cùng import shim fail-closed `scripts/patch_query_string_interop.cjs`; xcode→uuid **11.1.1** giữ nguyên. Không sửa thuật toán package, không force audit fix/suppress/downgrade.

## 3. Test/build/Docker/CI và bằng chứng

| Kiểm tra | Kết quả / bằng chứng |
|---|---|
| Backend/database local | **77 PASS**, không skip; PostGIS/OSRM/Traccar thật; `artifacts/m4-full-database.log` |
| Migration | Dev và container head **0005**; isolated upgrade/downgrade/upgrade thật, integration rerun **20 PASS**. Không downgrade database nghiệp vụ; `m4-migration-head.txt`, `m4-migration-container.txt` |
| M4 integration | Concurrent replay, RBAC/stable rejection, audit, GPS stale/invalid/duplicate, 50m/70m hysteresis, offline correction/stale arrival ID; `m4-focused-final.log` |
| Contract/lint/typecheck | Contract **4 PASS**, Ruff/format/mypy và frontend lint/typecheck PASS; core OR-Tools 9 test giữ nguyên |
| Frontend tests | Shared **7 PASS**, mobile **5 PASS**, gồm SQLite thật/restart/FIFO/concurrency/projection và decoder security regression |
| npm ci/compatibility | Clean npm 12.2.0 ci PASS; Expo install --check tương thích; `m4-npm-ci-final.log`, `m4-expo-compatibility.log` |
| Web build/runtime | PASS, **19** traces, không tham chiếu các package advisory; `m4-web-runtime-surface.json` |
| Android/iOS export/runtime | PASS, **1284/1150** sources, không chứa code advisory; `m4-mobile-runtime-surface.json`. Export không phải APK/IPA |
| Browser QA | PASS trên API/PostGIS/OSRM thật trong database QA riêng: route 375px không tràn; dừng API → correction offline → reconnect sync; 60m khóa, 71m re-arm, 49m ARRIVED mới; driver/dispatcher audit, reload không replay ARRIVED. `m4-ui-checks.json` và screenshots `m4-ui-*.png`; đã dọn đúng database QA |
| Docker/stack/health | Engine **29.7.2**, image cuối build/start **PASS**; api/admin-web/postgres/redis/minio/traccar/osrm **healthy**, minio-init exit **0**. API live/ready và Web 200, DB/Redis/storage/Traccar ready; MinIO versioning + signed read/write PASS, anonymous read 403; OSRM matrix/geometry **85 points PASS**. `m4-docker-final-resume.log`, `m4-containers.json`, `m4-stack-health.json`, `m4-osrm-health.json` |
| CI remote | Source **97e9d44**, [run 37697731979](https://github.com/phamdanghung/delivery-tracking/actions/runs/37697731979) **completed/success**: frontend và backend PASS; backend **77 PASS**, migration round-trip + **20 PASS** integration. Đã đọc log thực `m4-ci-frontend.log`, `m4-ci-backend.log`, metadata `m4-ci-status.json` |

Audit vẫn hiển thị **21 high**, 0 moderate/critical, lan truyền từ hai advisory braces/node-forge; `m4-npm-audit.json`, `m4-dependency-security.json` và tree. Decoder [GHSA-vcc3-ghjq-m6fr](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr) đã nâng upstream 0.5.0 và có regression/exports PASS. Hai advisory còn lại chưa có bản vá theo đối chiếu upstream ngày 07/10/2026: [braces](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), [node-forge](https://github.com/advisories/GHSA-86w9-cpqp-85rv).

Docker Desktop bị lỗi socket runtime cũ khi khởi động lại; đã giữ lại thư mục runtime cũ, tạo socket runtime mới và khôi phục engine. Không reset/xóa volumes hoặc dữ liệu. Build bị gián đoạn được tiếp tục bằng cache; health lấy sau khi Compose xác nhận healthy, không tính lần gọi sớm trong startup là PASS.

Đường dependency tiêu biểu: eslint-config-next → plugin → fast-glob → micromatch → braces; Expo → CLI → code-signing-certificates/node-forge; Expo → config-plugins → xcode → uuid 11.1.1. Đây là đường tooling liên quan advisory; không suy diễn rằng toàn bộ Expo/React Native là tooling. Runtime gates kiểm code đóng gói thực tế, không chỉ nhãn devDependencies. Giữ repo/config/cert đáng tin cậy, loopback/ports cần thiết, audit và runtime gates trong CI. DEC-033 chỉ áp dụng M3; chưa có chấp thuận M4. Mốc theo dõi đang có: muộn nhất **02/11/2026** hoặc trước production.

## 4. Điểm chưa xác minh

- Chưa chạy trên thiết bị Android/iOS vật lý, APK/IPA, airplane mode hoặc SQLite/SecureStore native trên thiết bị. Node SQLite thật, browser outage và native export không thay thế nghiệm thu thiết bị.
- Chưa chạy xe/GPS thực ngoài đường; AT-05 dùng vị trí giả lập qua luồng GPS server và PostGIS thật. Chưa mở ứng dụng gọi điện/chỉ đường trên thiết bị.
- Không xác minh production hoặc các chức năng M5 trở đi; không dùng kết quả M4 để phê duyệt production.

## 5. Quyết định cần chủ dự án

1. Có mở rộng chấp nhận tạm thời **braces GHSA-vfj7-8cjw-p6xm** và **node-forge GHSA-86w9-cpqp-85rv** sang M4 development/local/CI với các kiểm soát hiện có hay không. Không tự mở rộng DEC-033 và không coi advisory đã vá.
2. Chốt xử lý offline **409** khi điều phối đã thay đổi/hủy dữ liệu: hiện giữ ERROR và FIFO, hiển thị lỗi/thử lại nguyên command, không tự bỏ action/đổi payload/id. Receipt từ chối ổn định có thể chặn queue; chưa triển khai thao tác giải quyết conflict khi chưa có quyết định. Đề xuất tài xế đọc dữ liệu mới và liên hệ điều phối; cần khóa cách giải quyết queue nếu muốn tiếp tục các action sau.

Theo **CODEX_TOKEN_RULES.md §9**, “dừng đúng phần liên quan” khi thiếu nghiệp vụ/contract; phần xử lý conflict bổ sung dừng để chờ chốt. Các phần đã có quyết định và kiểm tra kỹ thuật được giữ nguyên.

## 6. Kết luận

**M4: FAIL — chưa đủ điều kiện đóng**, do accepted risk M4 và quy tắc giải quyết offline conflict chưa được chủ dự án chốt. Các kiểm tra kỹ thuật nêu trên **PASS**; các điểm chưa xác minh giữ rõ ở mục 4. Không tự kết luận PASS WITH CONDITIONS, không merge PR #3 và không chuyển M5.
