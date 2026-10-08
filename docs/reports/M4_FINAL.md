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
| Migration | Database development mới của project chuẩn: volume PostgreSQL được xác minh trống trước khởi tạo; `alembic upgrade head` áp dụng **0001 → 0002 → 0003 → 0004 → 0005 → 0006**, container head **0006**. Không sửa migration lịch sử. `m4-standard-migration.log`, `m4-standard-migration-chain.txt`, `m4-standard-migration-head.txt`. Bằng chứng isolated round-trip/integration **22 PASS** vẫn áp dụng; không downgrade database nghiệp vụ |
| Conflict integration | Cùng/khác entity, review stale, payload nguyên bản, RBAC, discard/replacement/replay/concurrent resolution và exact audit PASS |
| Frontend | Shared **7 PASS**, mobile **8 PASS**, SQLite thật: restart/offline/reconnect/lost response, dependent queue, independent sync, không duplicate và explicit replacement; lint/typecheck PASS |
| Browser QA | API/PostGIS/OSRM thật trên database QA riêng: offline hai action cùng stop và một action stop khác; stop độc lập ACK khi stop đầu 409; review/discard từng command; GPS 71m/49m re-arm; command mới liên kết rõ command cũ. Database xác nhận 2 conflict, 2 discard audit, 1 replacement, mỗi stop 1 DELIVERING, không FAILED giả. `m4-conflict-ui-proof.json`, screenshots `m4-ui-conflict-*.png`; database QA đã dọn đúng phạm vi |
| npm ci / audit / web / Android-iOS | Clean npm 12.2.0 ci PASS; audit đầy đủ 21 high từ hai advisory được DEC-035 chấp nhận, gate PASS. Web build PASS, 19 traces; Android/iOS export PASS, 1284/1150 sources. Runtime gates không phát hiện package advisory trong các bundle; export không phải APK/IPA |
| CI remote | Source `9c107f1` [run 37767991879](https://github.com/phamdanghung/delivery-tracking/actions/runs/37767991879) và commit tài liệu `e618f5f` [run 37784258287](https://github.com/phamdanghung/delivery-tracking/actions/runs/37784258287): **completed/success cả frontend/backend**. Đã đọc log thực; backend 79 + 22 PASS, shared 7/mobile 8 PASS. Revision này chỉ đổi báo cáo, tái sử dụng bằng chứng source theo CODEX_TOKEN_RULES.md §15 |
| Docker/stack/health | **Project chuẩn `fleet-delivery` PASS**: engine **29.7.2**; api/admin-web/postgres/redis/minio/traccar/osrm **healthy**, minio-init exit **0**; PostGIS **3.5.2**, head **0006**. API live/ready và Web/Traccar 200, Redis PONG; MinIO private/versioning và signed read/write PASS, anonymous read 403; OSRM matrix/geometry 85 points PASS. `m4-standard-containers.json`, `m4-standard-health.json`, `m4-standard-osrm-health.json`, `m4-standard-verification.json`. Tái sử dụng image đã build/PASS, không rebuild hoặc full regression khi source không đổi |

Khởi tạo development chuẩn theo quyết định chủ dự án ngày 08/10/2026: dùng Compose/migrations hiện có và script **`scripts/bootstrap_m1.py`** đã được README tài liệu hóa. Chỉ tạo ADMIN ứng dụng đầu tiên và tài khoản adapter trên Traccar mới; credentials giữ trong `.env` ignored, không in ra log. Database có 1 user ADMIN; vehicles/deliveries/trips/trip_stops/gps_snapshots/receipts/conflict resolutions đều 0. Web BFF login/me/list rỗng/logout PASS. Không tạo dữ liệu nghiệp vụ giả. Stack riêng được **stop**, giữ containers/volumes; không down/prune/reset.

## 4. Điểm chưa xác minh

- **Database development Docker cũ chưa được phục hồi** theo quyết định chủ dự án; không coi là production data. Các thư mục/runtime/disk/volume hiện còn được giữ nguyên, không xóa/prune/reset hoặc ghi đè runtime lưu trữ; kiểm tra 13 thư mục runtime lưu trữ, data disk còn tồn tại và tất cả tên volume trước khởi tạo vẫn còn (`m4-standard-preserved-before.json`, `m4-standard-verification.json`). Chưa xác minh khả năng phục hồi nội dung database cũ; không coi việc giữ các tài nguyên hiện còn là bằng chứng đã phục hồi. Database development mới/project chuẩn đã khởi tạo và xác minh riêng.
- Chưa nghiệm thu thiết bị Android/iOS vật lý, APK/IPA, airplane mode hoặc SQLite/SecureStore trên thiết bị; export/Node SQLite/browser outage không thay nghiệm thu thiết bị. Chưa thử GPS xe ngoài đường hoặc ứng dụng gọi/chỉ đường trên thiết bị.
- Không xác minh production/M5 trở đi.

## 5. Quyết định chủ dự án

- **DEC-035** đã phê duyệt accepted risk M4: braces **GHSA-vfj7-8cjw-p6xm**, node-forge **GHSA-86w9-cpqp-85rv**, chỉ development/local/CI. Audit vẫn hiển thị **21 high** lan truyền từ hai root advisory; không coi đã vá, không suppress. Dùng repo/config/cert đáng tin cậy; Metro/Compose loopback/phạm vi cần thiết; không force fix/downgrade; giữ audit và runtime gates. Review muộn nhất **02/11/2026** hoặc trước production; upstream patch hoặc runtime exposure yêu cầu đánh giá lại ngay. Không sửa DEC-023/024/029/033.
- **DEC-036** đã phê duyệt và triển khai quy tắc offline conflict. Hai quyết định nghiệp vụ/bảo mật không còn là blocker.
- Chủ dự án đã quyết định không phục hồi database development cũ tại thời điểm này, cho phép khởi tạo database development mới trên project chuẩn; giữ tài nguyên cũ hiện còn để có thể nghiên cứu phục hồi sau. Đã thực hiện và xác minh, không còn quyết định chặn việc đóng M4 development/local/CI.

## 6. Kết luận

**M4: PASS WITH ACCEPTED RISK theo DEC-035**, đủ điều kiện đóng trong phạm vi development/local/CI. DEC-036 đã đạt; database mới và project chuẩn được xác minh, không còn blocker trong phạm vi này. Các điểm chưa xác minh thiết bị/GPS thực và dữ liệu cũ vẫn nêu rõ; không phê duyệt production. Không merge PR #3, không chuyển M5.
