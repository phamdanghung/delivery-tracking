# Hệ thống quản lý và định vị xe giao hàng

M0 đã hoàn tất với accepted risk có điều kiện. M1 bổ sung đăng nhập/RBAC, người dùng, xe, hồ sơ tài xế và GPS Traccar thật theo nghiệp vụ V1.1, Technical Pack V1.0 và UX/UI V1.0. Chưa triển khai workflow giao hàng M2 hoặc customer tracking.

## Chạy môi trường local

Yêu cầu Docker Desktop với Linux Engine đang hoạt động và Python launcher có module `uv`. Từ thư mục dự án, chạy PowerShell:

```powershell
./scripts/dev.ps1
```

Lệnh tạo các secret còn thiếu trong `.env` bằng giá trị ngẫu nhiên, build image tuần tự, khởi động dependencies, chạy migration và bootstrap tài khoản đầu tiên trên database/Traccar mới rồi chờ stack sẵn sàng. Giữ các giá trị và tài khoản đã tồn tại, không reset mật khẩu. Đăng nhập web bằng `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD` trong `.env` local; đây chỉ là tài khoản khởi tạo dev. PostgreSQL local dùng `127.0.0.1:55433`, cấu hình qua `POSTGRES_PORT`.

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health/live
- Readiness: http://localhost:8000/health/ready
- Traccar local: http://localhost:8082
- MinIO console: http://localhost:9001 — thông tin đăng nhập trong `.env` local.

Các cổng Docker chỉ bind loopback. Đây là cấu hình dev; chưa dùng cho production hoặc thiết bị GPS thật. Bucket `fleet-pod` private và bật versioning. Traccar lưu GPS trong volume H2 riêng của môi trường local; database nghiệp vụ dùng PostgreSQL 16/PostGIS. Không reset Docker hoặc xóa volume để xử lý lỗi khởi động.

MinIO và mc build từ source chính thức đã cố định release/SHA vì các image public được kiểm tra không tải được. Lần build đầu có thể lâu do tải Go modules. Build Go giới hạn hai tác vụ và dùng cache; script build tuần tự để phù hợp máy có ít RAM. Kết quả xác minh thực tế được ghi trong `docs/reports/M0_FINAL.md`.

```powershell
docker compose ps
docker compose logs --tail 100 api
docker compose stop
```

## Chạy mã nguồn ngoài Docker

Yêu cầu Node.js 22.22.2+ (hoặc 24.15+/26+) và npm 12.2.0 và Python launcher có module `uv`. Backend cố định Python 3.12; `uv` quản lý interpreter và môi trường riêng.

```powershell
npx.cmd --yes npm@12.2.0 ci
npx.cmd --yes npm@12.2.0 run dev:web
```

App tài xế dùng React Native qua Expo theo template chính thức, không thay stack. M0 chạy Metro chỉ trên localhost; chưa mở LAN/tunnel. Chạy trên thiết bị/emulator tương thích với Expo SDK trong lockfile:

```powershell
npx.cmd --yes npm@12.2.0 run dev:mobile
```

Backend khi các dịch vụ phụ thuộc đã chạy:

```powershell
python -m uv sync --project apps/api --frozen --python 3.12.12
Set-Location apps/api
python -m uv run --frozen --env-file ../../.env alembic upgrade head
python -m uv run --frozen --env-file ../../.env uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

## Kiểm tra

```powershell
./scripts/verify.ps1
```

Script kiểm tra yêu cầu Docker stack đã bootstrap và đang chạy; tự tạo database **test riêng**, chạy toàn bộ test backend, gồm REST/WebSocket Traccar thật và feed OsmAnd mô phỏng, cùng vòng upgrade/downgrade/upgrade rồi xóa đúng database vừa tạo. Thiếu database hoặc Traccar là lỗi, không skip. Script cũng kiểm tra health thật và một object MinIO riêng rồi xóa chính version vừa tạo. Không chạy downgrade trên database vận hành.

Nếu chạy test thủ công, cần database **test riêng**, đã migrate:

```powershell
Set-Location apps/api
# Thiết lập DATABASE_URL và TEST_DATABASE_URL trỏ vào database test riêng.
python -m uv run --frozen alembic upgrade head
python -m uv run --frozen pytest
```

CI chạy lint, typecheck, test, build web, export bundle Android/iOS, migration upgrade/downgrade/upgrade và integration test PostGIS/Traccar bằng services thật riêng của run. `npm ci` vẫn hiển thị audit; không suppress findings. Export JavaScript bundle chưa thay thế build native APK/IPA hoặc kiểm thử điện thoại/GPS vật lý.

## Cấu trúc và truy vết

- `apps/api`: FastAPI, cấu hình ENV, health, migration và test.
- `apps/admin-web`: Next.js/TypeScript, màn hình nền tảng tiếng Việt.
- `apps/driver-mobile`: React Native/Expo, màn hình khởi tạo tiếng Việt.
- `packages/shared`: kiểu dữ liệu vận hành dùng chung và kiểm tra baseline.
- `db/migrations/0001_baseline.sql`: bản sao nguyên vẹn SQL đã cung cấp.
- `openapi/openapi.yaml`: bản sao nguyên vẹn OpenAPI nghiệp vụ.
- `openapi/m1.openapi.json` và `openapi/m2.openapi.json`: snapshot giữ nguyên để kiểm tra tương thích. `python -m uv run --project apps/api scripts/export_openapi.py` sinh contract M3 hiện tại vào `openapi/m3.openapi.json`.
- `infra/docker`, `compose.yaml`: dev stack.
- `docs/specifications`: toàn bộ Technical Pack được giải nén, giữ nguyên nội dung.
- `docs/requirements`: vấn đề phát hiện và truy vết M0.
- `docs/reports/M0_FINAL_REVISION.md`: kết quả xác minh mới nhất; `M0_FINAL.md` là báo cáo trước xử lý advisory/remote CI; `M0.md` lưu báo cáo ban đầu.
- `docs/requirements/M1_SCOPE.md`: phạm vi, bổ sung contract và giới hạn M1.
- `docs/reports/M1_FINAL.md`: báo cáo nghiệm thu M1 và các điểm chưa xác minh.

GPS dùng NORMAL <=30 giây, STALE >30 đến <=120 giây, LOST >120 giây. Bản tin fix cũ vừa tới không trở thành vị trí hiện tại. ACC thiếu → không xác định; speed Traccar đổi từ knots sang km/h. Hồ sơ tài xế liên kết xe qua Trip theo baseline, M1 chỉ đọc liên kết có sẵn.

ADMIN quản trị user/xe/mapping; DISPATCHER đọc fleet/GPS/history; DRIVER chỉ đọc tài khoản của mình trong M1. Web giữ token trong cookie HttpOnly qua BFF cùng origin, không lưu token vào localStorage. Với Traccar đã có tài khoản, điền credentials hợp lệ vào `.env`; bootstrap không tạo lại/reset server đã sử dụng. OSM basemap dành cho kiểm tra local với attribution; review provider/policy trước production.

Đọc `START_HERE_FOR_CODEX_V1.1.md` trước khi sửa source. Trước khi triển khai giao diện phải đọc toàn bộ `UX_UI_Design_Spec_V1.0/`. Tài liệu nghiệp vụ V1.1 có độ ưu tiên cao nhất; bộ UX/UI hướng dẫn điều hướng, luồng thao tác, component, design token và nghiệm thu giao diện, không thay thế hợp đồng nghiệp vụ/API/database.

## M2 — đơn và chuyến nháp

Áp dụng DEC-025–028 và `docs/requirements/M2_SCOPE.md`. Web `/deliveries` nhập đơn (nháp Zalo chỉ gợi ý), ba kiểu hẹn, timeline/audit, hủy có lý do và xác nhận giao lại. `/trips` lưu DRAFT với xe/tài xế/stops; chưa duyệt/xuất hoặc tối ưu tuyến. Quá tải chỉ cảnh báo.

Migration `0003` thêm trạng thái từng lần giao và đề xuất giao lại; baseline 0001/0002 giữ nguyên. `COMPANY_LATITUDE`/`COMPANY_LONGITUDE` trong `.env` cấu hình điểm công ty. Khi thiếu, web báo rõ và yêu cầu nhập điểm thay thế hợp lệ theo DEC-002; không tự geocode. Không đưa tọa độ giả vào cấu hình vận hành.

Driver chỉ thấy chuyến đã duyệt của mình và chỉ đề xuất lịch giao lại. Điều phối xác nhận mới cập nhật đơn; DELIVERED vẫn cần ảnh POD trên storage thật, upload thuộc M5. Xem `openapi/m2.openapi.json` và `docs/reports/M2_FINAL.md` để đối chiếu contract/kết quả nghiệm thu.

## M3 — tối ưu tuyến

Áp dụng DEC-030–032 và `docs/requirements/M3_SCOPE.md`. WEB-07 tại `/trips/{id}/optimize`: nhập/xác nhận giờ xuất phát, ghi đè service theo stop, xem route OSRM, km/thời gian, ETA và mức vi phạm. Kết quả vi phạm được lưu (HTTP 422) nhưng không được duyệt; không override. Kết quả cũ khi input/config/dataset đổi phải tối ưu lại. Quá tải vẫn warning; duyệt hợp lệ chuyển DRAFT → PLANNED và đơn PLANNED → ASSIGNED với audit.

`scripts/dev.ps1` chuẩn bị graph OSM thật và khởi động OSRM self-host, chỉ bind loopback. Nếu chuẩn bị riêng: `python scripts/prepare_osrm.py`, rồi `docker compose up -d --wait osrm`. Extract Saigon public dùng local/CI, được ghi nguồn/hash trong `artifacts/osrm/metadata.json`; không phải tọa độ công ty. Ghi attribution OSM/BBBike, ODbL. Thay vùng dữ liệu dùng `--url`/`--directory` riêng và cấu hình mount tương ứng, không tự gửi địa chỉ khách ra ngoài.

ENV `OSRM_URL`, `OSRM_METADATA_PATH`, `FIXED_TIME_TOLERANCE_SECONDS=900`, `DEFAULT_SERVICE_SECONDS=600`, `ROUTE_SOLVER_SECONDS=3`, `OSRM_TIMEOUT_SECONDS=10`. Metadata path tương đối được tính từ repo root; Compose dùng URL internal và mount read-only. Provider chỉ kết nối địa chỉ local/private, không proxy/redirect và không fallback. `scripts/verify_osrm.py` xác minh table/route thật bằng tọa độ fixture public, độc lập với điểm công ty cấu hình.

CI dùng extract đường thật có phiên bản tại `infra/osrm/fixtures/Saigon.osm.pbf`, kiểm SHA256 rồi tự dựng graph. Nguồn/ODbL ghi trong README cạnh file; tránh timeout nguồn tải công khai, không dùng mock. Có thể dùng cùng input local với `prepare_osrm.py --pbf infra/osrm/fixtures/Saigon.osm.pbf --sha256 305729efc04180b6a151ba3d61f6bb5c91b05ed044eed734b30f3625f806119b`.

OR-Tools giữ thứ tự tối ưu số điểm vi phạm → km → thời gian. Ngân sách solver cấu hình được; nếu hết thời gian trước khi chứng minh tối ưu toàn cục, kết quả nêu cảnh báo và mục tiêu đã chứng minh. Hard time gate vẫn kiểm tra trước duyệt. CI có OSRM/PostGIS/Traccar thật, giữ `npm ci` audit và các runtime-surface gates. M3 không mở M4; accepted risk M2 không tự áp dụng M3.
