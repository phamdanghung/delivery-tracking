# ADR 0001 Nền tảng M0

Ngày: 04/10/2026. Phạm vi: khởi tạo, không thêm nghiệp vụ.

Backend modular monolith dùng FastAPI/Python 3.12. Web dùng Next.js/TypeScript. App dùng React Native/TypeScript qua Expo, giữ khả năng phát triển native và bổ sung SQLite/outbox ở M4. PostgreSQL 16/PostGIS là database nghiệp vụ; Traccar là nguồn GPS thô. Redis và MinIO được chạy riêng bằng Compose.

Migration Alembic `0001` thực thi nguyên văn SQL Technical Pack. Không sửa schema đã cung cấp hoặc thêm ràng buộc nghiệp vụ khi chưa đủ quyết định. Downgrade chỉ phục vụ database test, giữ lại extension có thể dùng chung.

Traccar local dùng H2 trong volume riêng, phù hợp chạy dev. Không dùng cùng bảng/database với nghiệp vụ. Cổng giao thức OsmAnd 5055 được mở trên loopback để phục vụ giả lập local; giao thức phần cứng production sẽ xác định ở M1 theo thiết bị được chọn.

API M0 chỉ có `/health/live` và `/health/ready`. Readiness yêu cầu schema đã migrate, PostGIS, Redis, bucket ảnh và Traccar cùng hoạt động. OpenAPI nghiệp vụ gốc được giữ nguyên; API docs runtime hiện chỉ mô tả endpoint đã triển khai. Không thêm endpoint giả trả thành công.

Dependencies được khóa trong `package-lock.json`, `apps/api/uv.lock` và export requirements có hash để build Docker. Dùng Dockerfile Python riêng theo hướng dẫn chính thức FastAPI; web dùng Next.js App Router và Expo dùng template TypeScript chính thức.

Kiểm tra registry thực tế cho thấy image MinIO Docker Hub bị từ chối và tag Quay không tồn tại. Vì vậy MinIO và mc được build từ source chính thức, cố định release/tag object SHA và giữ LICENSE trong image. Source MinIO dùng RELEASE.2025-10-15T17-29-55Z; mc dùng RELEASE.2025-08-13T08-35-41Z. Đây là thay đổi cách đóng gói dev, không đổi object storage hoặc nghiệp vụ. Ngày 04/10/2026 đã build cả hai image, khởi động stack thật và xác minh bucket private/versioning cùng ghi/đọc có xác thực; kết quả ở `docs/reports/M0_FINAL.md`. Go build dùng cache và giới hạn hai tác vụ; script build tuần tự để giảm RAM. Build lần đầu lâu hơn dùng image có sẵn. Không dùng image fork bên thứ ba hoặc sản phẩm trả phí để thay thế.

Sau đối chiếu START_HERE V1.1 và toàn bộ UX/UI V1.0, web/mobile skeleton dùng `packages/shared/src/design-tokens.ts` cho style nền tảng. Không thêm workflow, quyền, trạng thái hoặc màn hình nghiệp vụ. PostgreSQL host dùng cổng cấu hình `POSTGRES_PORT`, mặc định 55433, để không ảnh hưởng service 5432 có sẵn; port nội bộ Docker vẫn 5432. Script kiểm tra tạo database/object riêng và chỉ xóa tài nguyên do chính lần kiểm tra tạo.

Nguồn kỹ thuật tham khảo: https://fastapi.tiangolo.com/deployment/docker/ ; https://nextjs.org/docs/app/getting-started/installation ; https://docs.expo.dev/get-started/create-a-project/ .
