# PROJECT_DECISIONS.md

> Nguồn quyết định đã khóa của dự án Fleet Delivery / Delivery Tracking.
> Mục đích: giúp Codex tra cứu nhanh các quyết định đã được chủ dự án chốt mà không phải lặp lại trong prompt.
> Nếu tài liệu khác mâu thuẫn với file này về một quyết định đã khóa, phải dừng phần liên quan và báo chủ dự án; không tự suy đoán hoặc tự đổi nghiệp vụ.

## 1. Nguyên tắc sử dụng

- Chỉ ghi các quyết định đã được chủ dự án chốt.
- Không dùng file này để thay thế toàn bộ Business Spec, Technical Pack hoặc UX/UI Spec.
- Không tự mở rộng quyết định sang phạm vi chưa được phê duyệt.
- Mọi thay đổi mới phải được chủ dự án chốt trước khi sửa file này.
- Milestone sau chỉ được bắt đầu khi milestone trước đã được review và cho phép tiếp tục.

## 2. Quy mô và cách vận hành hiện tại

- Đội xe hiện tại: 1 xe.
- Kiến trúc phải hỗ trợ ít nhất 3 xe mà không cần thiết kế lại.
- Sản lượng hiện tại: khoảng 5–7 điểm giao/ngày tại TP.HCM.
- Hiện tại đơn giao được chia sẻ qua Zalo cho bộ phận giao hàng.
- Giai đoạn đầu chưa tích hợp trực tiếp Zalo; ưu tiên nhập tay và sao chép/dán nhanh.

## 3. Quyết định nghiệp vụ đã khóa

### DEC-001 — Nhập đơn giao
- Chọn: A2.
- Hỗ trợ nhập đơn thủ công.
- Hỗ trợ sao chép/dán nhanh nội dung từ Zalo.
- Chưa tích hợp trực tiếp Zalo ở giai đoạn đầu.
- Có thể bổ sung Excel/hệ thống khác ở giai đoạn sau.

### DEC-002 — Điểm bắt đầu/kết thúc chuyến
- Chọn: B1.
- Mặc định xuất phát từ công ty/xưởng.
- Mặc định kết thúc tại công ty/xưởng.
- Điều phối được phép thay đổi điểm bắt đầu hoặc điểm kết thúc khi cần.

### DEC-003 — Loại thời gian hẹn giao
- Chọn: C3.
- Hỗ trợ 3 loại:
  1. Giờ cố định.
  2. Khung giờ.
  3. Giao trước một thời hạn.

### DEC-004 — Sửa trạng thái ARRIVED bị đánh dấu sai
- Chọn: D1.
- Tài xế và điều phối đều được phép sửa trạng thái ARRIVED bị đánh dấu sai.
- Bắt buộc audit: ai sửa, thời điểm sửa, giá trị cũ, giá trị mới, lý do sửa.

### DEC-005 — Hạn tracking link
- Chọn: E1.
- Tracking link hết hạn sau 1 giờ kể từ khi đơn chuyển sang DELIVERED.

### DEC-006 — Cảnh báo sai lệch nhiên liệu
- Chọn: F2.
- Cảnh báo khi nhiên liệu thực tế lệch quá 15% so với mức tính toán.

### DEC-007 — Cảnh báo ngoài giờ
- Chọn: G2.
- Cảnh báo hoạt động ngoài giờ từ 18:00 đến 07:30 sáng hôm sau.

### DEC-008 — Chu kỳ bảo dưỡng
- Chọn: H2.
- Chu kỳ bảo dưỡng phải cấu hình được riêng cho từng xe.

### DEC-009 — Gửi tracking link cho khách
- Chọn: I4.
- Hệ thống tạo tracking link.
- Nhân viên gửi thủ công cho khách qua Zalo.
- Chưa tự động gửi SMS/Zalo ZNS trong giai đoạn đầu.

## 4. Giao hàng thất bại và hẹn giao lại

### DEC-010 — Luồng giao thất bại
- Cho phép giao thất bại và hẹn lại.
- Luồng chuẩn: FAILED → ghi lý do → đề xuất/chọn thời gian mới → điều phối xác nhận → quay lại hàng đợi điều phối/lập kế hoạch.

### DEC-011 — Quyền hẹn giao lại
- Chọn: A1.
- Tài xế được phép đề xuất thời gian giao lại.
- Tài xế không được tự chốt lịch giao lại.
- Điều phối phải xác nhận thì lịch mới có hiệu lực.
- Không tự mở quyền reschedule đầy đủ cho tài xế.

## 5. Quyết định về tuyến đường

### DEC-012 — Thứ tự ưu tiên tối ưu tuyến
Bắt buộc ưu tiên theo đúng thứ tự:
1. Đúng thời gian đã hẹn với khách.
2. Ít km hơn.
3. Nhanh hơn.

Không được đảo thứ tự ưu tiên này.

### DEC-013 — Quá tải
- Nếu chuyến/xe có dấu hiệu quá tải: chỉ cảnh báo.
- Không tự động chặn chuyến.

## 6. GPS và trạng thái xe

### DEC-014 — Geofence ARRIVED
- Bán kính geofence: 50 m.
- Khi xe đi vào vùng 50 m quanh điểm giao, hệ thống có thể tự đánh dấu ARRIVED theo thiết kế đã khóa.
- Việc sửa ARRIVED sai phải theo DEC-004.

### DEC-015 — GPS freshness
- Chọn: C1.
- NORMAL: 0–30 giây kể từ lần cập nhật gần nhất.
- STALE: 31 giây đến 2 phút.
- LOST: trên 2 phút.
- Phải dùng nhất quán trong backend, API, web điều phối và cảnh báo liên quan.
- Không hiển thị vị trí cũ như thể đó là vị trí hiện tại.

### DEC-016 — Khách xem vị trí xe
- Khách được xem vị trí GPS thực tế của xe đang giao đơn của mình.
- Khách không được xem xe khác, đơn khác, lịch sử đội xe hoặc dữ liệu nội bộ không liên quan.

## 7. e-POD

### DEC-017 — Bằng chứng giao hàng
- Ảnh là đủ để làm e-POD trong phạm vi hiện tại.
- Chữ ký điện tử không bắt buộc.
- Ảnh POD phải lưu private và liên kết đúng với đơn giao.

## 8. Cảnh báo an toàn

### DEC-018 — Trạng thái safety alert
- Chọn: B1.
- Trạng thái chính thức:
  - NEW = Mới
  - SEEN = Đã xem
  - RESOLVED = Đã xử lý
- Không được gộp SEEN và RESOLVED.
- Nếu schema/API hiện tại chưa biểu diễn đủ 3 trạng thái, phải điều chỉnh bằng migration/contract phù hợp tại milestone liên quan; không sửa âm thầm.

## 9. State machine giao hàng

### DEC-019 — Luồng trạng thái chính
Luồng chuẩn:
CREATED → PLANNED → ASSIGNED → EN_ROUTE → ARRIVED → DELIVERING → DELIVERED

Nhánh thất bại:
FAILED → RESCHEDULED → PLANNED

Các trạng thái/hành động hủy chỉ áp dụng theo tài liệu nghiệp vụ đã khóa; không tự bổ sung transition ngoài contract.

## 10. Driver App và offline

### DEC-020 — Offline driver app
- App tài xế phải cache route/đơn cần thiết, xếp hàng action khi offline, đồng bộ lại khi có mạng và tránh gửi trùng.
- Mỗi action đồng bộ phải có `client_action_id` hoặc cơ chế idempotency tương đương đã khóa.
- Không được để cùng một thao tác tạo ra nhiều event trùng khi reconnect.

## 11. Bảo mật và giới hạn tính năng

### DEC-021 — Remote immobilization
- Không triển khai remote vehicle immobilization trong Phase 1.
- Không thêm API hoặc UI điều khiển khóa xe từ xa trong M1–M8 nếu chưa có quyết định mới.

### DEC-022 — Tracking privacy
- Tracking token chỉ truy cập đúng giao hàng tương ứng.
- Không để token lộ dữ liệu đội xe hoặc khách khác.
- Token phải hết hạn theo DEC-005.

## 12. Kiến trúc kỹ thuật đã chọn

Các lựa chọn đã khóa:
- Backend: FastAPI / Python.
- Web Admin: Next.js + TypeScript.
- Driver App: React Native.
- Database: PostgreSQL + PostGIS.
- GPS platform: Traccar.
- Route optimization: OR-Tools.
- Cache/queue/idempotency hỗ trợ: Redis.
- Object storage private: S3-compatible / MinIO cho local.
- Không dùng microservices ở quy mô hiện tại nếu không có lý do được duyệt.

## 13. M0 — Quyết định chấp nhận rủi ro bảo mật

### DEC-023 — Accepted Risk cho M0
Chủ dự án đã phê duyệt có điều kiện hai advisory:
- braces — GHSA-vfj7-8cjw-p6xm
- node-forge — GHSA-86w9-cpqp-85rv

Phạm vi:
- chỉ M0;
- development/local/CI hiện tại;
- không áp dụng cho production;
- không miễn trừ các kiểm soát bảo mật khác.

Điều kiện:
- chỉ dùng repo/config/cert đáng tin cậy;
- Metro chỉ local/loopback;
- Docker/Compose không expose không cần thiết;
- không dùng `npm audit fix --force`;
- không suppress/ẩn advisory;
- tiếp tục giữ npm audit trong CI/report.

Review lại:
- trước ngày 03/11/2026, tức muộn nhất 02/11/2026; hoặc
- trước khi triển khai production;
- chọn mốc nào đến trước.

Nếu upstream có bản vá sớm hơn:
- ưu tiên nâng cấp;
- chạy lại npm ci, build, export, test, Docker/stack/health và CI.

Nếu advisory đi vào runtime attack surface thực tế:
- dừng phần liên quan;
- đánh giá lại;
- không suy rộng accepted risk của M0.

Trạng thái M0:
- PASS WITH ACCEPTED RISK.

### DEC-024 — Accepted Risk cho M1
- Ngày chốt: 05/10/2026.
- Milestone liên quan: M1.
- Quyết định: chủ dự án phê duyệt chấp nhận tạm thời braces GHSA-vfj7-8cjw-p6xm và node-forge GHSA-86w9-cpqp-85rv; M1 **PASS WITH ACCEPTED RISK**.
- Phạm vi: chỉ M1 và development/local/CI hiện tại.
- Không áp dụng cho: production hoặc milestone khác. Không xem advisory là đã được vá, không miễn trừ kiểm soát bảo mật khác.
- Ghi chú: quyết định riêng cho M1; giữ nguyên DEC-023 và lịch sử M0. Không tự chuyển sang M2.

Điều kiện bắt buộc:
- chỉ dùng repo/config/cert đáng tin cậy;
- Metro chỉ local/loopback;
- Docker không expose service không cần thiết;
- không dùng `npm audit fix --force`;
- không downgrade Expo/React Native chỉ để làm audit về 0;
- không suppress hoặc che advisory;
- tiếp tục giữ npm audit và runtime-surface gates trong CI/report.

Theo dõi:
- Review trước 03/11/2026, tức muộn nhất 02/11/2026, hoặc trước production, tùy mốc nào đến trước.
- Nếu upstream có bản vá sớm hơn: ưu tiên nâng cấp và chạy lại đầy đủ npm ci, build, Android/iOS export, test, Docker/stack/health và CI remote.
- Nếu advisory xuất hiện trong runtime attack surface thực tế ở milestone sau: dừng phần liên quan và đánh giá lại, không suy rộng quyết định này.

### DEC-025 — M2 chỉ lưu chuyến nháp (M2-1 / D1)
- Ngày chốt: 05/10/2026.
- Milestone liên quan: M2/M3.
- Quyết định: M2 cho tạo/lưu chuyến nháp, chọn xe, tài xế và các điểm giao; chưa mở nút duyệt/xuất chuyến trên web.
- Phạm vi: sau M3 có tối ưu tuyến và ETA mới cho duyệt/xuất chuyến.
- Ghi chú: giữ lịch sử các quyết định cũ, không giả ETA hoặc bỏ bước duyệt UX.

### DEC-026 — Điểm đầu/cuối cấu hình (M2-2 / E2)
- Ngày chốt: 05/10/2026.
- Milestone liên quan: M2.
- Quyết định: điểm đầu/cuối mặc định lấy từ ENV/config; không hard-code tọa độ, không tự geocode qua provider.
- Phạm vi: nếu chưa có tọa độ công ty/xưởng, hiển thị thiếu cấu hình và chưa cho lưu chuyến hoàn chỉnh cần điểm đầu/cuối.
- Ghi chú: điều phối vẫn được thay điểm đầu/cuối theo DEC-002.

### DEC-027 — Quyền hủy đơn M2 (M2-3)
- Ngày chốt: 05/10/2026.
- Milestone liên quan: M2.
- Quyết định: ADMIN/DISPATCHER được hủy đơn CREATED, PLANNED, ASSIGNED; bắt buộc lý do và audit đầy đủ.
- Không áp dụng cho: DRIVER hoặc các trạng thái khác.

### DEC-028 — Sửa ARRIVED để M4 (M2-4)
- Ngày chốt: 05/10/2026.
- Milestone liên quan: M2/M4.
- Quyết định: M2 không triển khai sửa ARRIVED nhận sai hoặc transition ngược đặc biệt.
- Phạm vi: giữ chức năng cho M4 khi triển khai geofence/ARRIVED theo DEC-004.

### DEC-029 — Accepted Risk cho M2
- Ngày chốt: 06/10/2026.
- Milestone liên quan: M2.
- Quyết định: chủ dự án phê duyệt CHẤP NHẬN TẠM THỜI rủi ro của `braces GHSA-vfj7-8cjw-p6xm` và `node-forge GHSA-86w9-cpqp-85rv` cho M2 development/local/CI.
- Phạm vi: chỉ M2 và môi trường development/local/CI hiện tại.
- Không áp dụng cho: production hoặc milestone khác. Không xem advisory là đã vá, không miễn trừ các kiểm soát bảo mật khác.
- Ghi chú: quyết định riêng cho M2; giữ nguyên DEC-023/024 và lịch sử. M2 được kết luận PASS WITH ACCEPTED RISK; không tự merge PR hoặc chuyển M3.

Điều kiện bắt buộc:
- chỉ dùng repo/config/cert đáng tin cậy;
- Metro và Docker/Compose chỉ expose trong phạm vi cần thiết/loopback;
- không dùng `npm audit fix --force`;
- không downgrade Expo/React Native chỉ để làm audit về 0;
- không suppress hoặc ẩn advisory;
- tiếp tục giữ npm audit và runtime-surface gates trong CI/report.

Theo dõi:
- Review muộn nhất **02/11/2026** hoặc trước production, tùy mốc nào đến trước.
- Nếu upstream có bản vá sớm hơn: ưu tiên nâng cấp và chạy lại đầy đủ npm ci, build, Android/iOS export, test, Docker/stack/health và CI remote.
- Nếu advisory đi vào runtime attack surface thực tế ở milestone sau: dừng phần liên quan và đánh giá lại; không tự suy rộng exception.

### DEC-030 — Thời gian tối ưu M3
- Ngày chốt: 06/10/2026.
- Milestone liên quan: M3.
- Quyết định: FIXED_TIME mặc định ±15 phút quanh giờ hẹn; dung sai cấu hình được, không hard-code business logic. Service time mặc định 10 phút/điểm, cấu hình/ghi đè được.
- Phạm vi: planned_departure_at do điều phối nhập hoặc xác nhận trước tối ưu; UI được gợi ý nhưng không tự lưu khi chưa xác nhận.
- Không áp dụng cho: TIME_WINDOW và BEFORE_DEADLINE dùng chính xác thời gian đã nhập, không thêm dung sai FIXED_TIME.

### DEC-031 — Routing OSRM self-host M3
- Ngày chốt: 06/10/2026.
- Milestone liên quan: M3.
- Quyết định: OSRM self-host local/CI; dùng /table/v1/driving cho ma trận quãng đường/thời gian, /route/v1/driving cho geometry/detail. URL lấy ENV/config.
- Phạm vi: OSRM unavailable trả lỗi rõ; không fallback khoảng cách chim bay âm thầm.
- Không áp dụng cho: geocoding tự động, Google Maps API, gửi địa chỉ khách ra provider ngoài trong M3.

### DEC-032 — Hard time constraints và duyệt chuyến M3
- Ngày chốt: 06/10/2026.
- Milestone liên quan: M3.
- Quyết định: cam kết FIXED_TIME/TIME_WINDOW/BEFORE_DEADLINE là HARD CONSTRAINT khi duyệt/xuất. Kết quả vi phạm được lưu/hiển thị rõ stop và mức vi phạm, nhưng KHÔNG được duyệt/xuất.
- Phạm vi: điều phối phải điều chỉnh dữ liệu rồi tối ưu lại; M3 không cho manual override hard time violation. Duyệt tuyến theo WEB-07/DEC-025 chỉ khi kết quả còn hợp lệ và không vi phạm.
- Ghi chú: quá tải vẫn chỉ WARNING, không chặn duyệt theo DEC-013. Không sửa DEC cũ.

### DEC-033 — Accepted Risk cho M3
- Ngày chốt: 07/10/2026.
- Milestone liên quan: M3.
- Quyết định: chủ dự án phê duyệt CHẤP NHẬN TẠM THỜI rủi ro của `braces GHSA-vfj7-8cjw-p6xm` và `node-forge GHSA-86w9-cpqp-85rv` cho M3 development/local/CI; M3 **PASS WITH ACCEPTED RISK**.
- Phạm vi: chỉ M3 và môi trường development/local/CI hiện tại.
- Không áp dụng cho: production hoặc milestone khác. Không xem advisory là đã vá, không miễn trừ các kiểm soát bảo mật khác.
- Ghi chú: quyết định mới riêng cho M3; giữ nguyên DEC-023/024/029 và toàn bộ lịch sử. Không tự merge PR #2 hoặc chuyển M4.

Điều kiện bắt buộc:
- chỉ dùng repo/config/cert đáng tin cậy;
- Metro/Compose chỉ expose trong phạm vi cần thiết/loopback;
- không dùng `npm audit fix --force`;
- không downgrade Expo/React Native chỉ để audit về 0;
- không suppress hoặc ẩn advisory;
- tiếp tục giữ npm audit và runtime-surface gates trong CI/report.

Theo dõi:
- Review muộn nhất **02/11/2026** hoặc trước production, tùy mốc nào đến trước.
- Nếu upstream có bản vá sớm hơn: ưu tiên nâng cấp và chạy lại đầy đủ npm ci, build, Android/iOS export, test, Docker/stack/health và CI remote.
- Nếu advisory đi vào runtime attack surface thực tế ở milestone sau: dừng phần liên quan và đánh giá lại; không tự suy rộng quyết định này.

## 14. Milestone boundaries

### M0
Foundation / repo / Docker / database / migration / skeleton / CI / health.

### M1
Users / vehicles / drivers / GPS / Traccar / telemetry / GPS status.

### M2
Deliveries / trips / trip stops / state machine / assignment / failed delivery / reschedule.

### M3
Route optimization.

### M4
Driver App / offline / geofence / sync.

### M5
e-POD.

### M6
Customer tracking / ETA.

### M7
Fuel / expenses / maintenance / safety alerts.

### M8
Reporting / security hardening / performance / backup-restore / final acceptance.

Quy tắc:
- Không tự triển khai sâu milestone sau khi milestone hiện tại chưa được review.
- Mỗi milestone phải có báo cáo FINAL và trạng thái PASS/FAIL/PASS WITH CONDITIONS nếu được chủ dự án cho phép.

## 15. Quy tắc khi phát hiện mâu thuẫn tài liệu

Thứ tự xử lý:
1. Không tự đoán.
2. Xác định rõ tài liệu nào mâu thuẫn.
3. Kiểm tra xem PROJECT_DECISIONS.md đã có quyết định khóa hay chưa.
4. Nếu đã có: áp dụng quyết định đã khóa.
5. Nếu chưa có hoặc vẫn không đủ rõ: dừng phần liên quan và báo chủ dự án.
6. Không thay đổi schema/API/UX để “tự làm cho khớp”.

## 16. Mẫu cập nhật file này

Khi có quyết định mới, thêm theo mẫu:

### DEC-XXX — Tên quyết định
- Ngày chốt:
- Milestone liên quan:
- Quyết định:
- Phạm vi:
- Không áp dụng cho:
- Ghi chú:

Không sửa/xóa quyết định cũ mà không có chỉ thị của chủ dự án; nếu thay đổi, ghi quyết định mới và đánh dấu quyết định cũ là SUPERSEDED.
