# Vấn đề tài liệu và môi trường

Ngày rà soát: 04/10/2026. Đã đọc START_HERE, bản nghiệp vụ DOCX V1.1, bản kỹ thuật DOCX V1.0 và toàn bộ 11 file Technical Pack. Không thay đổi bản gốc.

## DOCX kỹ thuật đánh số nghiệm thu khác nhau

Phần 12 DOCX kỹ thuật liệt kê AT-01 đến AT-15 với nội dung khác bộ `08_KIEM_THU_NGHIEM_THU.md`. Phần 16 của chính DOCX dùng AT-01 đến AT-16 khớp cách đánh số Technical Pack nhưng không khớp phần 12. Ví dụ phần 12 gọi AT-02 là tạo 7 đơn, trong khi phần 16 gắn ROUT-01 với AT-03; file 08 gọi AT-02 là GPS cũ và AT-03 là tạo 7 đơn.

M0 ghi truy vết bằng mã M0 riêng. Với nghiệp vụ sau này, đề xuất thống nhất mã theo file 08 và ma trận CSV vì chúng khớp nhau; luôn đối chiếu nội dung với bản nghiệp vụ V1.1. Không đổi tiêu chí nghiệp vụ. Cần chủ dự án chốt quy ước mã khi cập nhật baseline kỹ thuật.

## OpenAPI còn thiếu chi tiết

`04_OPENAPI.yaml` chỉ khai báo endpoint và response description, thiếu request/response schema và thiếu path parameters tại POD, reschedule, optimize, start. Một số endpoint xuất hiện trong ma trận CSV nhưng chưa có trong OpenAPI: history, odometer, fuel profiles, maintenance và documents.

M0 giữ nguyên bản sao contract. Trước milestone triển khai liên quan cần bổ sung contract có phiên bản và xác nhận nội dung cần quyết định; không tự suy đoán trường bắt buộc/quyền/trạng thái.

## Mô hình dữ liệu chưa đồng nhất hoàn toàn

File 02 có `TripStop.status`, DriverProfile.phone và Delivery.time_commitment_type, nhưng SQL file 03 không có hai trường đầu và dùng tên `commitment_type`. SQL cũng chưa có bảng daily aggregates trong CSV, hoặc bảng idempotency/outbox. M0 áp dụng nguyên văn SQL. Các bổ sung thuộc milestone sau, cần thống nhất contract trước khi thay đổi schema đã khóa.

## Quy tắc chưa đủ thông tin cho milestone sau

- M3: ngưỡng đúng giờ của FIXED_TIME, thời gian phục vụ điểm, nguồn bản đồ và tọa độ công ty/xưởng chưa có giá trị chính thức.
- M1: thiết bị/protocol GPS, ngưỡng stale GPS và lọc GPS nhảy chưa có cấu hình đã chốt.
- M2/M4: tập trạng thái cho phép sửa ARRIVED và xử lý xung đột đồng bộ cần contract cụ thể; quyền tài xế chọn giao lại trong nghiệp vụ cần đối chiếu endpoint reschedule chỉ ADMIN/DISPATCHER trong DOCX kỹ thuật.
- M6: thời hạn token trước DELIVERED chưa được quy định dù SQL yêu cầu expires_at NOT NULL.
- M7: nguồn kỳ đối soát nhiên liệu và xử lý mẫu số bằng 0, cấu hình ngoại lệ ngoài giờ, ngưỡng tốc độ cần làm rõ trước triển khai phần liên quan.

Các vấn đề này không cản trở việc dựng source M0. Không triển khai các phần phụ thuộc trước khi chủ dự án chốt.

## Docker Desktop local

Docker CLI có sẵn nhưng Linux Engine chưa hoạt động. Đã thử `docker desktop start` và mở Docker Desktop; backend thoát với lỗi không truy cập được `C:/Users/user/AppData/Local/Docker/run/sailor-ingest.sock`. Chưa reset Docker, xóa socket hoặc xóa dữ liệu của người dùng. Migration và dev stack cần kiểm tra lại khi Docker Engine hoạt động.

Manifest lookup của PostGIS/Traccar đạt. MinIO Docker Hub bị từ chối truy cập; các tag MinIO Quay đã thử không còn manifest. Compose được chuyển sang build MinIO/mc từ release/SHA chính thức, giữ nguyên stack. Đã kiểm chứng tag nguồn qua Git nhưng chưa build image vì Engine chưa hoạt động.

## Repository

Đã khởi tạo Git trên nhánh `codex/m0-foundation`. Chưa có remote được cung cấp, nên chưa thể tạo PR hoặc xác nhận CI chạy trên server. Workflow có trong source để dùng khi repository được kết nối.
