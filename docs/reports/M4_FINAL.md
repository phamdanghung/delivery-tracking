# M4 FINAL

Ngày cập nhật: **08/10/2026**. Source `9c107f1a3659dd8a2b278db11c0a3c1d48dbbf70`, branch `codex/m4-driver-offline-geofence`, base M3 merge `8d95b1c7c08df79f24335526c9e2763a02309e29`. [Draft PR #3](https://github.com/phamdanghung/delivery-tracking/pull/3), chưa merge. Không chuyển M5.

## 1. Phần đã triển khai

- Driver App: chuyến/stop của chính tài xế, route/cam kết/ETA/timeline, gọi và chỉ đường bằng tọa độ; SQLite cache/outbox theo owner, SecureStore native, web preview cache/queue localStorage và token trong bộ nhớ. Persist trước khi báo lưu, sync reconnect/foreground, cache ACK trước SYNCED; receipt theo actor/client_action_id giữ nguyên kết quả replay và audit.
- DEC-034: geofence server dùng GPS Traccar hợp lệ/fresh và PostGIS thật; sửa ARRIVED → EN_ROUTE có lý do/audit, trip ACTIVE, khóa auto-ARRIVED đến GPS mới >70m rồi lần vào ≤50m. Không timeout hoặc transition ngược khác.
- **DEC-036**: 409 → CONFLICT, giữ payload/id; chỉ chặn chuỗi phụ thuộc cùng entity, entity khác tiếp tục. Server cấp review token từ dữ liệu mới và kiểm lại trước quyết định bỏ; quyết định có lý do được persist/retry idempotently sau restart/lost response. Giữ DISCARDED và audit actor/time/action/conflict/reason. Tài xế chọn rõ command cũ cần liên kết, tạo command mới từ trạng thái hiện tại với ID mới; không tự replay payload cũ hoặc tự gắn mọi hành động tương lai thành replacement.
- Không thay state machine/RBAC/POD gate M1–M3, không thêm camera/POD upload, Customer Tracking hoặc chi phí M5–M7. Snapshot contract cũ giữ nguyên.

## 2. File/migration/API chính

- `apps/api/app/driver.py`, `geofence.py`, `gps.py`, `main.py`; migration **0005_m4_driver_actions** và **0006_m4_conflict_resolution**. Receipt, geofence state và conflict resolution/audit được lưu trên database thật.
- API M4 `/api/v1/driver/today`, `/driver/actions`, `/driver/conflicts/review`, `/driver/conflicts/resolve`, `/deliveries/{id}/arrival-correction`; contract additive `openapi/m4.openapi.json`.
- Mobile `src/app`, `src/driver`, `src/offline` và tests; Web correction tại delivery detail; `PROJECT_DECISIONS.md`, `M4_SCOPE.md`, `M4_TRACEABILITY.md`, README và CI audit gate.
- Expo **57.0.27**, React Native **0.86.3**, React **19.2.3** giữ nguyên. Decoder upstream **0.5.0** với shim CJS fail-closed; xcode → uuid **11.1.1**. Revision conflict không thêm dependency.

## 3. Test/build/Docker/CI và bằng chứng

| Kiểm tra | Kết quả |
|---|---|
| Backend/database | **79 PASS**, không skip; PostGIS/OSRM/Traccar thật; `artifacts/m4-conflict-full-database.log` |
| Migration | Database kiểm tra head **0006**; isolated upgrade/downgrade/upgrade thật và integration rerun **22 PASS**; không downgrade database nghiệp vụ |
| Conflict integration | Cùng/khác entity, review stale, payload nguyên bản, RBAC, discard/replacement/replay/concurrent resolution và exact audit PASS |
| Frontend | Shared **7 PASS**, mobile **8 PASS**, SQLite thật: restart/offline/reconnect/lost response, dependent queue, independent sync, không duplicate và explicit replacement; lint/typecheck PASS |
| Browser QA | API/PostGIS/OSRM thật trên database QA riêng: offline hai action cùng stop và một action stop khác; stop độc lập ACK khi stop đầu 409; review/discard từng command; GPS 71m/49m re-arm; command mới liên kết rõ command cũ. Database xác nhận 2 conflict, 2 discard audit, 1 replacement, mỗi stop 1 DELIVERING, không FAILED giả. `m4-conflict-ui-proof.json`, screenshots `m4-ui-conflict-*.png`; database QA đã dọn đúng phạm vi |
| npm ci / audit / web / Android-iOS | Clean npm 12.2.0 ci PASS; audit đầy đủ 21 high từ hai advisory được DEC-035 chấp nhận, gate PASS. Web build PASS, 19 traces; Android/iOS export PASS, 1284/1150 sources. Runtime gates không phát hiện package advisory trong các bundle; export không phải APK/IPA |
| CI remote | [Run 37767991879](https://github.com/phamdanghung/delivery-tracking/actions/runs/37767991879), source `9c107f1`: **completed/success cả frontend/backend**. Đã đọc log thực `m4-ci-frontend.log`, `m4-ci-backend.log`, metadata `m4-ci-status.json`; backend 79 + 22 PASS, shared 7/mobile 8 PASS |
| Docker/stack/health | Engine **29.7.2**, full build/start **PASS** trên project riêng `fleet-m4-verification`; api/admin-web/postgres/redis/minio/traccar/osrm **healthy**, minio-init exit **0**. Container head **0006**; API live/ready, Web/Traccar 200, DB/Redis/storage ready; MinIO versioning và signed read/write PASS, anonymous read 403; OSRM matrix/geometry 85 points PASS. `m4-conflict-stack-build.log`, `m4-conflict-containers.json`, `m4-conflict-migration-container.txt`, `m4-conflict-stack-health.json`, `m4-conflict-osrm-health.json`. Không coi kết quả project riêng là khôi phục dữ liệu project chuẩn |

## 4. Điểm chưa xác minh

- Docker Desktop sau khởi động nhận datastore trống, không nhận các image/volume development cũ. Không có lệnh reset/prune/xóa volume; giữ các thư mục runtime đã đổi tên. Chưa chứng minh khôi phục dữ liệu cũ. Project chuẩn có volume mới trống nhưng **chưa khởi tạo database**; chờ chủ dự án quyết định phục hồi dữ liệu cũ hay cho phép database development mới. Stack kiểm tra dùng project/volumes riêng.
- Chưa nghiệm thu thiết bị Android/iOS vật lý, APK/IPA, airplane mode hoặc SQLite/SecureStore trên thiết bị; export/Node SQLite/browser outage không thay nghiệm thu thiết bị. Chưa thử GPS xe ngoài đường hoặc ứng dụng gọi/chỉ đường trên thiết bị.
- Không xác minh production/M5 trở đi.

## 5. Quyết định chủ dự án

- **DEC-035** đã phê duyệt accepted risk M4: braces **GHSA-vfj7-8cjw-p6xm**, node-forge **GHSA-86w9-cpqp-85rv**, chỉ development/local/CI. Audit vẫn hiển thị **21 high** lan truyền từ hai root advisory; không coi đã vá, không suppress. Dùng repo/config/cert đáng tin cậy; Metro/Compose loopback/phạm vi cần thiết; không force fix/downgrade; giữ audit và runtime gates. Review muộn nhất **02/11/2026** hoặc trước production; upstream patch hoặc runtime exposure yêu cầu đánh giá lại ngay. Không sửa DEC-023/024/029/033.
- **DEC-036** đã phê duyệt và triển khai quy tắc offline conflict. Hai quyết định nghiệp vụ/bảo mật không còn là blocker.
- Còn chờ quyết định về dữ liệu development Docker cũ. Theo CODEX_TOKEN_RULES.md §9, dừng đúng phần có thể ảnh hưởng dữ liệu; không tự khởi tạo project chuẩn.

## 6. Kết luận

**M4: FAIL — chưa đủ điều kiện đóng**, chỉ còn blocker về dữ liệu development Docker cũ: cần chủ dự án chốt phục hồi dữ liệu cũ hoặc cho phép khởi tạo database development mới. Source, test/build/export/CI và full stack riêng đều PASS; accepted risk M4 đã được DEC-035 phê duyệt, conflict DEC-036 đã đạt. Sau khi giải quyết blocker dữ liệu và xác minh project chuẩn, có thể kết luận **PASS WITH ACCEPTED RISK**. Không merge PR #3, không chuyển M5.
