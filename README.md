# Hệ thống quản lý và định vị xe giao hàng

Nền tảng M0 theo bản nghiệp vụ V1.1 đã khóa và Technical Pack V1.0. Chưa có chức năng điều phối, đăng nhập hoặc tracking khách; các phần đó được triển khai theo M1–M8 sau khi M0 đạt tiêu chí thoát.

## Chạy môi trường local

Yêu cầu Docker Desktop với Linux Engine đang hoạt động. Từ thư mục dự án, chạy PowerShell:

```powershell
./scripts/dev.ps1
```

Lệnh tạo `.env` với mật khẩu ngẫu nhiên nếu chưa có, build image tuần tự, chạy migration và chờ dịch vụ sẵn sàng. Không ghi đè `.env` đã tồn tại. PostgreSQL local dùng `127.0.0.1:55433`, cấu hình qua `POSTGRES_PORT`, để tránh cổng 5432 đang được service khác sử dụng.

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

Script kiểm tra yêu cầu Docker stack đang chạy; tự tạo database **test riêng**, chạy toàn bộ 11 test backend cùng vòng upgrade/downgrade/upgrade và xóa đúng database vừa tạo. Thiếu database là lỗi, không skip. Script cũng kiểm tra health thật và ghi/đọc một object MinIO riêng rồi xóa chính version vừa tạo. Không chạy downgrade trên database có dữ liệu vận hành.

Nếu chạy test thủ công, cần database **test riêng**, đã migrate:

```powershell
Set-Location apps/api
# Thiết lập DATABASE_URL và TEST_DATABASE_URL trỏ vào database test riêng.
python -m uv run --frozen alembic upgrade head
python -m uv run --frozen pytest
```

CI chạy lint, typecheck, unit test, build web, export bundle Android/iOS, migration upgrade/downgrade/upgrade và test PostGIS trên database test riêng. Export JavaScript bundle chưa thay thế build native APK/IPA hoặc kiểm thử trên điện thoại.

## Cấu trúc và truy vết

- `apps/api`: FastAPI, cấu hình ENV, health, migration và test.
- `apps/admin-web`: Next.js/TypeScript, màn hình nền tảng tiếng Việt.
- `apps/driver-mobile`: React Native/Expo, màn hình khởi tạo tiếng Việt.
- `packages/shared`: kiểu dữ liệu vận hành dùng chung và kiểm tra baseline.
- `db/migrations/0001_baseline.sql`: bản sao nguyên vẹn SQL đã cung cấp.
- `openapi/openapi.yaml`: bản sao nguyên vẹn OpenAPI nghiệp vụ; chưa triển khai endpoint M1–M8.
- `infra/docker`, `compose.yaml`: dev stack.
- `docs/specifications`: toàn bộ Technical Pack được giải nén, giữ nguyên nội dung.
- `docs/requirements`: vấn đề phát hiện và truy vết M0.
- `docs/reports/M0_FINAL_REVISION.md`: kết quả xác minh mới nhất; `M0_FINAL.md` là báo cáo trước xử lý advisory/remote CI; `M0.md` lưu báo cáo ban đầu.

Đọc `START_HERE_FOR_CODEX_V1.1.md` trước khi sửa source. Trước khi triển khai giao diện phải đọc toàn bộ `UX_UI_Design_Spec_V1.0/`. Tài liệu nghiệp vụ V1.1 có độ ưu tiên cao nhất; bộ UX/UI hướng dẫn điều hướng, luồng thao tác, component, design token và nghiệm thu giao diện, không thay thế hợp đồng nghiệp vụ/API/database.
