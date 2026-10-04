# Hệ thống quản lý và định vị xe giao hàng

Nền tảng M0 theo bản nghiệp vụ V1.1 đã khóa và Technical Pack V1.0. Chưa có chức năng điều phối, đăng nhập hoặc tracking khách; các phần đó được triển khai theo M1–M8 sau khi M0 đạt tiêu chí thoát.

## Chạy môi trường local

Yêu cầu Docker Desktop với Linux Engine đang hoạt động. Từ thư mục dự án, chạy PowerShell:

```powershell
./scripts/dev.ps1
```

Lệnh tạo `.env` với mật khẩu ngẫu nhiên nếu chưa có, build image, chạy migration và chờ dịch vụ sẵn sàng. Không ghi đè `.env` đã tồn tại.

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health/live
- Readiness: http://localhost:8000/health/ready
- Traccar local: http://localhost:8082
- MinIO console: http://localhost:9001 — thông tin đăng nhập trong `.env` local.

Các cổng Docker chỉ bind loopback. Đây là cấu hình dev; chưa dùng cho production hoặc thiết bị GPS thật. Bucket `fleet-pod` private và bật versioning. Traccar lưu GPS trong volume H2 riêng của môi trường local; database nghiệp vụ dùng PostgreSQL 16/PostGIS. Không reset Docker hoặc xóa volume để xử lý lỗi khởi động.

MinIO và mc build từ source chính thức đã cố định release/SHA vì các image public được kiểm tra không tải được. Lần build đầu có thể lâu do tải Go modules. Dockerfile này chưa được build xác minh tại máy hiện tại vì Docker Engine lỗi; xem báo cáo M0 trước khi nghiệm thu.

```powershell
docker compose ps
docker compose logs --tail 100 api
docker compose stop
```

## Chạy mã nguồn ngoài Docker

Yêu cầu Node.js 22.13+ và Python launcher có module `uv`. Backend cố định Python 3.12; `uv` quản lý interpreter và môi trường riêng.

```powershell
npm.cmd ci
npm.cmd run dev:web
```

App tài xế dùng React Native qua Expo theo template chính thức, không thay stack. Chạy trên thiết bị/emulator tương thích với Expo SDK trong lockfile:

```powershell
npm.cmd run dev:mobile
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

Integration test cần database **test riêng**, đã migrate. Không chạy downgrade trên database có dữ liệu vận hành:

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
- `docs/reports/M0.md`: kết quả kiểm tra và phần còn lại.

Đọc `START_HERE_FOR_CODEX.md` trước khi sửa source. Tài liệu nghiệp vụ V1.1 có độ ưu tiên cao nhất.
