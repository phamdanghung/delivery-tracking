# M5 FINAL — e-POD bằng ảnh

Ngày xác minh: **09/10/2026**. Branch `codex/m5-e-pod`; base M4 đã nghiệm thu: `32cd5872507dd3f9a56a059c2c0ff7086e87e8eb`. Source chức năng: `7cd726245587f0c4cc437302d994e6d8da9192f7`; cập nhật DEC-040/041, canonical config và CI gate: `424379c8053fecdcf7f97bb1b17c360eb406855b`. Draft PR [#4](https://github.com/phamdanghung/delivery-tracking/pull/4), chưa merge.

## 1. Phạm vi đã triển khai

- Áp dụng **DEC-037/038/039**: camera/album, lưu ảnh bền vững trước ACK, upload sau reconnect qua outbox M4 và `client_action_id` cố định; receipt/idempotency giữ thứ tự POD → DELIVERED. Conflict vẫn theo DEC-036, không đổi command cũ hoặc khóa entity độc lập.
- Private MinIO/S3 với object immutable/version cụ thể, kiểm tra bytes/MIME/dung lượng/pixel/SHA-256; retry không tạo photo/version/audit/event trùng. DRIVER được phân công upload; người dùng có quyền đọc delivery mới được lấy metadata/signed URL ngắn hạn. Web chi tiết đơn có ảnh và provenance; không public POD cho khách.
- GPS hợp lệ lưu tọa độ/fix time/freshness; thiếu/stale/invalid vẫn cho hoàn tất nếu POD và điều kiện khác hợp lệ, nhưng cần xác nhận lý do `LOCATION_UNVERIFIED` và audit. Không tọa độ giả/GPS cũ. Camera/album có nguồn riêng; không tin EXIF GPS/time, bỏ EXIF không cần thiết và giữ orientation/pixel rendering.
- Backend chỉ mở gate DELIVERED bằng POD của **trip stop/lượt giao hiện tại**. Reschedule cần POD mới; ảnh cũ giữ lịch sử. Không bắt buộc chữ ký, không triển khai M6 hoặc sửa state machine đã khóa.

## 2. File, database và API chính

- Backend: `apps/api/app/pod*.py`, `deliveries.py`, `driver.py`, `config.py`, `main.py`; Pillow **12.3.0**, dependency lock đồng bộ.
- App: `src/pod/PhotoCapture.tsx`, durable files/IndexedDB assets, `driver/context.tsx`, M4 outbox/stop detail; bổ sung Expo ImagePicker/FileSystem/Location tương thích SDK **57**, giữ React Native **0.86**. Web: `app/dispatch/pod.tsx`, workspace detail.
- Migration **0007_m5_pod** bổ sung attempt/source/GPS/provenance/hash/object version/metadata cho `pod_photos`; không đoán metadata ảnh lịch sử, không sửa migration 0001–0006.
- `POST/GET /api/v1/deliveries/{id}/pod/photos`; `GET /api/v1/deliveries/{id}/pod/photos/{photo_id}/url`; thêm command POD_UPLOAD vào `/driver/actions`. Contract M5: `openapi/m5.openapi.json`, `docs/requirements/M5_CONTRACT.md`; snapshots M1–M4 giữ nguyên, có kiểm tra tương thích.
- Quyết định và scope: `PROJECT_DECISIONS.md`, `M5_SCOPE.md`. **DEC-040** accepted risk riêng cho M5; **DEC-041** canonical runtime. CI giữ toàn bộ audit và runtime-surface gates; không sửa DEC accepted-risk cũ.

## 3. Test/build/CI có bằng chứng

CI trước phê duyệt [run 37923064298](https://github.com/phamdanghung/delivery-tracking/actions/runs/37923064298) đã xác minh source chức năng, frontend chỉ lỗi audit. Run sau DEC-040/041: [37929097490](https://github.com/phamdanghung/delivery-tracking/actions/runs/37929097490), SHA `424379c8053fecdcf7f97bb1b17c360eb406855b`, **completed/success; frontend và backend PASS**. Đã đọc/lưu logs thực tế `artifacts/m5-ci-frontend.log`, `m5-ci-backend.log` và status JSON. Commit FINAL chỉ cập nhật tài liệu, tái sử dụng bằng chứng source/config theo CODEX_TOKEN_RULES §15.

| Kiểm tra | Kết quả |
| --- | --- |
| Backend CI | **PASS**: Ruff/format/mypy; **108 test PASS**, không skip. Database/PostGIS, MinIO private/versioned, Traccar và OSRM thật |
| Migration CI | **PASS**: upgrade head 0007 → downgrade base → upgrade 0007; **25 integration PASS** sau round-trip |
| POD | GPS hợp lệ và missing/stale/invalid; camera/album; EXIF sai/giả trên JPEG/PNG/WebP; POD lượt cũ/reschedule; concurrent/retry/lost response; 1 object version/audit/event; receipt replay; private read 403 và signed read 200 |
| Offline queue | Mobile **10 PASS**, shared **7 PASS**: restart/reconnect, POD trước DELIVERED, conflict cùng entity tạm dừng và entity khác tiếp tục, không replay ID mới |
| Frontend CI trước audit | **PASS**: clean npm **12.2.0 ci**, lint/typecheck, test, web build, Android/iOS export và cả hai runtime gates |
| Security audit | Vẫn **21 high** từ hai advisory tooling chưa vá; **DEC-040 accepted-risk gate local PASS**, không suppress. In/lưu đầy đủ npm audit; advisory mới, production hoặc quá hạn review bị từ chối; runtime web/native gates PASS |
| CI sau phê duyệt | **PASS cả frontend/backend**, run 37929097490; 108 test và 25 integration sau migration round-trip PASS. Audit JSON đầy đủ và gate DEC-040/runtime gates PASS; không dùng local test thay CI remote |
| Local | POD units **25 PASS**, lint/typecheck/Ruff/format/mypy PASS; web/native exports đã PASS. Full Windows 107 PASS/1 timing FAIL: test 30-stop **5.031s** so với ngưỡng 5s; cùng source/test đã PASS trong full CI Linux. Không sửa/skip test hoặc nới ngưỡng |

## 4. Docker/local development

**Canonical stack `fleet-delivery-dev` PASS theo DEC-041**: PostgreSQL/PostGIS **3.5.2**, Redis, MinIO, Traccar, OSRM, API và admin-web đều **healthy**; minio-init exit **0**. API live/ready và Web/Traccar **200**, Redis **PONG**, MinIO private/versioning Enabled, signed read/write PASS và anonymous read **403**. OSRM matrix và route geometry **PASS (85 điểm)**. Reuse đúng image source M5 đã build/PASS, không rebuild toàn bộ vì đổi project name. Bằng chứng: `artifacts/m5-canonical-containers.json`, `m5-canonical-health.json`, `m5-canonical-verification.json`, `m5-canonical-osrm.log`.

Database canonical mới trên volumes **fleet-delivery-dev_*** riêng đã áp dụng **0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007**, head **0007**; không sửa migration lịch sử. `m5-canonical-migration.log`/`m5-canonical-migration-chain.txt` và verification JSON xác minh chain/head/schema. Bootstrap `scripts/bootstrap_m1.py` chỉ tạo ADMIN và tài khoản adapter Traccar; **vehicles/deliveries/trips/trip_stops/POD/receipts/conflict resolutions = 0**. Login/me/list rỗng/logout qua Web BFF PASS. Không seed nghiệp vụ giả; không downgrade database development. Reuse canonical runtime từ milestone tiếp theo, chỉ migrate tiến lên; migration round-trip chỉ trên test DB.

Docker Engine **29.7.2** đã khôi phục sau lỗi socket Windows. Các thư mục socket lỗi được giữ dưới tên `.preserved-m5-20261009`/`-attempt2`; không delete/prune/factory reset, không xóa data disk/volume.

Stack **fleet-delivery head 0005 = PRESERVED/LEGACY** theo DEC-041, không dùng làm canonical và không coi là production data. Đã stop, giữ containers/volumes/runtime, không migrate/reset/prune/xóa/ghi đè dữ liệu. Các tên volume có trước lượt này, 13 thư mục runtime lưu trữ và data disk vẫn tồn tại; không tuyên bố nội dung database cũ đã phục hồi. `m5-legacy-preserved-containers.json`/`m5-canonical-retained-volumes.txt` là bằng chứng lưu trữ.

Stack thử **fleet-m5-development** đã cleanup đúng phạm vi sau khi canonical đạt: chỉ containers/network/volumes có prefix project test đó, không đụng legacy/canonical hoặc project khác (`m5-isolated-cleanup.log`). `compose.yaml` mặc định và `scripts/dev.ps1` dùng **fleet-delivery-dev**; README chỉ rõ reuse canonical, legacy và cleanup test. Không tạo runtime milestone mới thay canonical.

## 5. Chưa xác minh / quyết định cần chủ dự án

- Chưa QA camera/quyền/GPS/offline trên **thiết bị Android/iOS vật lý**, kill/restart khi picker đang mở và chạy giao thực tế. Export và tests không được gọi là bằng chứng phần cứng đã PASS.
- **DEC-040** đã phê duyệt riêng M5 development/local/CI cho **braces GHSA-vfj7-8cjw-p6xm** và **node-forge GHSA-86w9-cpqp-85rv**, thuộc Metro/Expo tooling; không có trong runtime web traces/native source maps đã kiểm tra. Audit 21 high là dependency lan truyền, không phải 21 advisory độc lập. Không coi đã vá, không suppress, không force fix/downgrade Expo/RN; không áp dụng production.
- Giữ repo/config/cert đáng tin cậy, loopback/phạm vi expose cần thiết, audit/runtime gates; review muộn nhất **02/11/2026** hoặc trước production, mốc nào sớm hơn. Upstream patch hoặc runtime exposure phải đánh giá lại ngay, ưu tiên patch và xác minh lại các bước liên quan. Không sửa DEC accepted-risk cũ.
- DEC-041 đã giải quyết lựa chọn runtime chuẩn; chưa xác minh khả năng phục hồi nội dung legacy và không coi việc giữ tài nguyên là bằng chứng đã phục hồi. Không còn quyết định nghiệp vụ/runtime chưa chốt trong phạm vi M5.

## 6. Kết luận và chạy lại

**M5: PASS WITH ACCEPTED RISK theo DEC-040**, đủ điều kiện đóng trong phạm vi development/local/CI. Canonical **fleet-delivery-dev** theo DEC-041 đã được khởi tạo/xác minh; không còn blocker trong phạm vi nghiệm thu này. Các advisory chưa vá và điểm chưa xác minh thiết bị/legacy vẫn được công khai, không áp dụng production. Không merge PR #4, không chuyển M6.

Lệnh kiểm tra: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build:web`, `npm run build:mobile`, `npm audit`; backend từ `apps/api`: `uv run --frozen pytest`. Integration bắt buộc dùng database/bucket test riêng và PostgreSQL/PostGIS/MinIO/OSRM/Traccar thật; migration downgrade chỉ trên database test, tuyệt đối không trên database nghiệp vụ. Local harness: `apps/api/.venv/Scripts/python.exe scripts/verify_database.py`; không chạy vào runtime cũ đang được bảo toàn.
