# M5 FINAL — e-POD bằng ảnh

Ngày xác minh: **09/10/2026**. Branch `codex/m5-e-pod`; base M4 đã nghiệm thu: `32cd5872507dd3f9a56a059c2c0ff7086e87e8eb`. Source kiểm tra: `7cd726245587f0c4cc437302d994e6d8da9192f7`. Draft PR [#4](https://github.com/phamdanghung/delivery-tracking/pull/4), chưa merge.

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
- Quyết định và scope: `PROJECT_DECISIONS.md`, `M5_SCOPE.md`. CI giữ audit và runtime-surface gates, không kế thừa risk M4.

## 3. Test/build/CI có bằng chứng

CI source thực tế: [run 37923064298](https://github.com/phamdanghung/delivery-tracking/actions/runs/37923064298), đúng SHA source nêu trên; logs đã lưu trong `artifacts/m5-ci-backend.log` và `m5-ci-frontend.log` (ignored).

| Kiểm tra | Kết quả |
| --- | --- |
| Backend CI | **PASS**: Ruff/format/mypy; **108 test PASS**, không skip. Database/PostGIS, MinIO private/versioned, Traccar và OSRM thật |
| Migration CI | **PASS**: upgrade head 0007 → downgrade base → upgrade 0007; **25 integration PASS** sau round-trip |
| POD | GPS hợp lệ và missing/stale/invalid; camera/album; EXIF sai/giả trên JPEG/PNG/WebP; POD lượt cũ/reschedule; concurrent/retry/lost response; 1 object version/audit/event; receipt replay; private read 403 và signed read 200 |
| Offline queue | Mobile **10 PASS**, shared **7 PASS**: restart/reconnect, POD trước DELIVERED, conflict cùng entity tạm dừng và entity khác tiếp tục, không replay ID mới |
| Frontend CI trước audit | **PASS**: clean npm **12.2.0 ci**, lint/typecheck, test, web build, Android/iOS export và cả hai runtime gates |
| Security audit CI | **FAIL**: 21 high propagated findings từ hai advisory tooling chưa được vá/chấp nhận cho M5 |
| CI tổng | **FAIL**, chỉ bước frontend `npm audit` lỗi; backend success. Không dùng local test thay CI remote |
| Local | POD units **25 PASS**, lint/typecheck/Ruff/format/mypy PASS; web/native exports đã PASS. Full Windows 107 PASS/1 timing FAIL: test 30-stop **5.031s** so với ngưỡng 5s; cùng source/test đã PASS trong full CI Linux. Không sửa/skip test hoặc nới ngưỡng |

## 4. Docker/local development

**Stack `fleet-m5-development` PASS**: PostgreSQL/PostGIS **3.5.2**, Redis, MinIO, Traccar, OSRM, API và admin-web đều **healthy**; minio-init exit **0**. API live/ready và Web/Traccar **200**, Redis **PONG**, MinIO private/versioning Enabled, signed read/write PASS và anonymous read **403**. Image API/Web M5 đã build; hash module POD trong container trùng source. Bằng chứng: `artifacts/m5-development-containers.json`, `m5-stack-health.json`, `m5-development-verification.json`, `m5-docker-api-final-build2.log`, `m5-docker-web-build.log`.

Database development mới trên volume riêng đã áp dụng **0001 → 0007**, head **0007**. Bootstrap `scripts/bootstrap_m1.py` chỉ tạo ADMIN và tài khoản adapter Traccar; **vehicles/deliveries/trips/trip_stops/POD/receipts/conflict resolutions = 0**. Login/me/list rỗng/logout qua Web BFF PASS. Không seed nghiệp vụ giả; không downgrade database development. Full regression và migration round-trip của cùng source dùng bằng chứng CI tại mục 3 theo CODEX_TOKEN_RULES §15.

Docker Engine **29.7.2** đã khôi phục sau lỗi socket Windows. Các thư mục socket lỗi được giữ dưới tên `.preserved-m5-20261009`/`-attempt2`; không delete/prune/factory reset, không xóa data disk/volume.

Engine hiện thấy stack `fleet-delivery` có head **0005**, khác bằng chứng M4 head 0006/PostGIS 3.5.2. Đã dừng bước API/migration trước khi thay schema database này và stop các dependency của stack đó; containers/volumes vẫn giữ. Không tuyên bố đã phục hồi database cũ hoặc đã xác minh project chuẩn hiện tại. Các tên volume có trước lượt này, 13 thư mục runtime lưu trữ trước đó và data disk vẫn tồn tại; chưa xác minh nội dung dữ liệu/runtime khác. Stack **`fleet-m5-development`** dùng volume mới riêng, source/Compose và migrations chuẩn, override image names local nằm trong `artifacts/m5-development.compose.json`; không thay kiến trúc/source Compose chuẩn.

## 5. Chưa xác minh / quyết định cần chủ dự án

- Chưa QA camera/quyền/GPS/offline trên **thiết bị Android/iOS vật lý**, kill/restart khi picker đang mở và chạy giao thực tế. Export và tests không được gọi là bằng chứng phần cứng đã PASS.
- Database/project chuẩn ở Engine hiện tại không khớp snapshot M4 đã nghiệm thu; cần xác định runtime chuẩn hoặc chọn stack development mới trước khi coi canonical stack đã xác minh. Giữ các dữ liệu/runtime cũ để phục hồi sau theo chỉ thị trước.
- **DEC-035 chỉ áp dụng M4**, không tự mở rộng M5. Hai advisory còn lại: **braces GHSA-vfj7-8cjw-p6xm** và **node-forge GHSA-86w9-cpqp-85rv**, thuộc Metro/Expo tooling; không có trong runtime web traces/native source maps đã kiểm tra. Audit 21 high là các dependency bị lan truyền, không phải 21 advisory độc lập. Không coi đã vá, không suppress, không force fix/downgrade Expo/RN.
- Nếu chủ dự án chấp nhận tạm thời M5 development/local/CI, cần DEC mới; giữ repo/config/cert đáng tin cậy, loopback/phạm vi expose cần thiết, audit/runtime gates; review muộn nhất **02/11/2026** hoặc trước production, mốc nào sớm hơn; upstream patch hoặc runtime exposure phải đánh giá lại. Chưa có phê duyệt production.

## 6. Kết luận và chạy lại

**M5: FAIL — chưa đủ điều kiện đóng**, do risk M5 chưa được phê duyệt và xác minh canonical runtime còn khác biệt. Source chức năng và backend CI đạt; không tự chuyển M6, không merge PR.

Lệnh kiểm tra: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build:web`, `npm run build:mobile`, `npm audit`; backend từ `apps/api`: `uv run --frozen pytest`. Integration bắt buộc dùng database/bucket test riêng và PostgreSQL/PostGIS/MinIO/OSRM/Traccar thật; migration downgrade chỉ trên database test, tuyệt đối không trên database nghiệp vụ. Local harness: `apps/api/.venv/Scripts/python.exe scripts/verify_database.py`; không chạy vào runtime cũ đang được bảo toàn.
