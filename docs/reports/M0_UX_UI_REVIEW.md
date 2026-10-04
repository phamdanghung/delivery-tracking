# Đối chiếu M0 với hướng dẫn V1.1 và UX/UI V1.0

> Cập nhật sau lượt tiếp tục M0: đã áp dụng token chung, typography/spacing/radius web và mobile; kiểm tra web ở năm kích thước không tràn ngang, web build và Android/iOS export đạt. Docker, database, migration và toàn bộ test đã xác minh thật. M0 vẫn FAIL vì dependency advisory chưa xử lý; CI remote CHƯA XÁC MINH. Xem **[M0 FINAL](M0_FINAL.md)**. Phần dưới giữ kết quả rà soát trước khi triển khai các điều chỉnh này.

Ngày rà soát: 04/10/2026. Tiếp nối commit M0 `e028212`, nhánh `codex/m0-foundation`.

## Tài liệu đã đọc đầy đủ

`START_HERE_FOR_CODEX_V1.1.md` nằm trong ZIP UX/UI được bổ sung, đã được giải nén vào thư mục gốc. Không khôi phục file START_HERE cũ đã bị người dùng xóa.

Toàn bộ thư mục `UX_UI_Design_Spec_V1.0/`:

1. `00_README_UX_UI.md` — mục đích, phạm vi, thứ tự ưu tiên và nguyên tắc frontend.
2. `01_KIEN_TRUC_THONG_TIN.md` — sidebar/topbar web, ba mục app tài xế, tracking không menu, URL đề xuất.
3. `02_USER_FLOWS.md` — bảy luồng điều phối, giao hàng, sửa ARRIVED, tracking, nhiên liệu, offline.
4. `03_WIREFRAME_SPEC.md` — bố cục web/mobile/tracking và trạng thái hiển thị bắt buộc.
5. `04_DESIGN_SYSTEM.md` — màu, typography, spacing, radius, form, badge, bản đồ, GPS, offline, accessibility.
6. `05_SCREEN_BY_SCREEN_SPEC.md` — WEB-01..14, DRV-01..08, CUS-01..03.
7. `06_UI_UX_ACCEPTANCE_TESTS.md` — 20 tiêu chí UX, responsive và điều kiện nghiệm thu màn hình.
8. `UX_UI_Design_Spec_He_thong_Quan_ly_Dinh_vi_Xe_giao_hang_V1.0.docx` — đã đọc toàn bộ nội dung, gồm 567 đoạn OOXML; chứa bản tổng hợp cùng các wireframe.

Đối chiếu source frontend, package shared, ADR, báo cáo M0, OpenAPI, SQL baseline và vấn đề đã ghi trước đó. Không đánh giá giao diện nghiệp vụ chưa tồn tại như đã hoàn tất.

## Kết luận về M0

Không có mâu thuẫn buộc làm lại kiến trúc, backend hoặc database M0. Next.js App Router, React Native/Expo, FastAPI, PostGIS, Redis, Traccar và MinIO vẫn phù hợp. Bộ UX/UI không yêu cầu thay stack. SQL/OpenAPI hiện vẫn bằng baseline gốc.

Web mới có trang khởi tạo `/`; app mới có một View khởi tạo; chưa có dashboard, điều hướng nghiệp vụ, workflow hoặc Customer Tracking. Vì vậy không có luồng nghiệp vụ đã code cần phá bỏ. Chưa có layout/sidebar sai cần chuyển kiến trúc. Sidebar/topbar, ba mục Hôm nay/Chi phí/Tài khoản, route `/t/{trackingToken}` và component dùng chung sẽ được bổ sung theo đúng milestone.

## Phần cần điều chỉnh

| Phần hiện tại | Đối chiếu tài liệu mới | Cách xử lý |
| --- | --- | --- |
| `apps/admin-web/app/globals.css` | H1 32–52px, H2 24px, body 17px, card radius 16px; khác web title 24/32, section 18/28, body 14–16/22–24, card radius 12px trong file 04 | Đồng bộ style nền tảng trước khi triển khai màn hình chính; không làm lại app |
| `apps/driver-mobile/App.tsx` | Title 36px, padding 28px, margin 20px; khác mobile title 22/28 và thang spacing được liệt kê trong file 04 | Dùng token chung và typography mobile theo spec trong phần nền tảng frontend |
| Màu web/mobile | Dùng literal màu riêng, chưa có design token tái sử dụng | Chuẩn hóa theo token file 04; màu accent được ghi là đề xuất, không coi đây là thay đổi nghiệp vụ |
| README | Còn trỏ tới START_HERE cũ đã xóa | Đã cập nhật sang V1.1 và thêm yêu cầu đọc toàn bộ UX/UI |
| Component/trạng thái frontend | Chưa có component dùng chung, loading/empty/error/permission/offline/stale GPS cho màn hình dữ liệu | Phần chưa triển khai, không phải logic sai đang chạy; phải bổ sung và nghiệm thu theo UX trước khi tuyên bố màn hình hoàn tất |

Lần rà soát này chỉ giải nén tài liệu, cập nhật README và ghi báo cáo. Chưa sửa CSS, app, nghiệp vụ, API, schema hoặc dependencies.

## Các điểm cần thống nhất trước milestone liên quan

1. **Hẹn giao lại của tài xế:** file UX 02 mục 3 và file 05 DRV-06 cho tài xế chọn thời gian giao lại. DOCX kỹ thuật phần 6 ghi endpoint reschedule chỉ ADMIN/DISPATCHER. Đây là sai khác tài liệu đã được ghi từ M0, không phải lỗi code vì endpoint chưa triển khai. Ưu tiên nghiệp vụ V1.1 và cần thống nhất quyền/contract trước M2/M4; không tự mở quyền API.
2. **Trạng thái cảnh báo:** file UX 05 WEB-12 yêu cầu Mới/Đã xem/Đã xử lý. SQL `safety_alerts` hiện chỉ có `acknowledged_by` và `acknowledged_at`, chưa biểu diễn rõ cả ba trạng thái. Không tự coi Đã xem là Đã xử lý; cần thống nhất semantics/schema/API trước M7.
3. **GPS:** file UX 04 mục 11 bổ sung hiển thị bình thường khi dữ liệu dưới 30 giây; ngưỡng stale/mất tín hiệu vẫn là cấu hình chưa có giá trị đầy đủ trong contract. Không dùng 30 giây làm ngưỡng mất kết nối mặc định nếu chưa được chốt; cần định nghĩa trước M1.

Không điểm nào trên cản trở kiểm tra hạ tầng M0. Không tự sửa nghiệp vụ hoặc hợp đồng kỹ thuật để khớp UX/UI cấp ưu tiên thấp hơn.

## Trạng thái và bước tiếp theo

M0 vẫn chưa hoàn tất. Kết quả kiểm tra trước cập nhật tài liệu: 9 test backend và 1 test baseline đạt, 2 integration test database chưa chạy; lint/typecheck, web build và bundle Android/iOS đạt. Không chạy lại các test này trong lượt chỉ rà soát tài liệu, không báo chúng là kết quả mới.

Đã kiểm tra lại `docker info`: Linux Engine vẫn chưa hoạt động. Migration/database, Docker image build (bao gồm MinIO/mc source build), dev stack và CI remote chưa được xác minh. Repository vẫn chưa có remote. Cảnh báo dependency trong báo cáo M0 chưa được xử lý.

Tiếp tục M0 tại phần đang dở: chuẩn hóa token/style nền tảng, xử lý Docker/dependency và kiểm tra migration cùng stack thực tế. Không khởi tạo lại repository, không làm lại baseline, không triển khai sâu Web Admin/App/Tracking và chưa chuyển M1 trước khi đủ điều kiện thoát.
