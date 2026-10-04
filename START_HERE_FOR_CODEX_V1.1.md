# START_HERE_FOR_CODEX

## Mục đích
Đây là tài liệu hướng dẫn khởi động dự án **Hệ thống Quản lý & Định vị Xe Giao hàng**.

Trước khi viết bất kỳ mã nguồn nào, Codex phải đọc toàn bộ tài liệu được liệt kê bên dưới, hiểu phạm vi dự án, quy tắc nghiệp vụ, kiến trúc, dữ liệu, API, màn hình, kiểm thử và kế hoạch triển khai.

Không được bắt đầu code khi chưa đọc đầy đủ tài liệu.

---

# 1. THỨ TỰ ƯU TIÊN TÀI LIỆU

Khi có khác biệt hoặc mâu thuẫn giữa các tài liệu, áp dụng thứ tự ưu tiên sau:

## Mức 1 — Nguồn sự thật nghiệp vụ cao nhất
**Dac_ta_nghiep_vu_He_thong_Quan_ly_Dinh_vi_Xe_giao_hang_V1.1_DA_KHOA.docx**

Tài liệu này là bản nghiệp vụ đã được chủ dự án duyệt và khóa.

Mọi chức năng, trạng thái, quy tắc nghiệp vụ, quyền người dùng và hành vi hệ thống phải tuân theo tài liệu này.

**Không được tự ý thay đổi nghiệp vụ.**

---

## Mức 2 — Đặc tả kỹ thuật tổng hợp
**Dac_ta_ky_thuat_He_thong_Quan_ly_Dinh_vi_Xe_giao_hang_cho_Codex_V1.0.docx**

Tài liệu này chuyển các yêu cầu nghiệp vụ đã khóa thành kiến trúc và yêu cầu kỹ thuật để triển khai.

Nếu nội dung trong tài liệu kỹ thuật khác với bản nghiệp vụ V1.1, phải ưu tiên bản nghiệp vụ V1.1 và báo lại điểm khác biệt.

---

## Mức 3 — Bộ Technical Pack
Đọc toàn bộ các file sau:

1. `00_README.md`
2. `01_KIEN_TRUC_HE_THONG.md`
3. `02_MO_HINH_DU_LIEU.md`
4. `03_DATABASE_SCHEMA.sql`
5. `04_OPENAPI.yaml`
6. `05_TRANG_THAI_VA_QUY_TAC.md`
7. `06_DAC_TA_MAN_HINH.md`
8. `07_BAO_MAT_HIEU_NANG_VAN_HANH.md`
9. `08_KIEM_THU_NGHIEM_THU.md`
10. `09_KE_HOACH_CODEX.md`
11. `10_MA_TRAN_TRUY_VET.csv`

Các file này là hướng dẫn chi tiết để triển khai source code.

---

## Mức 4 — Bộ UX/UI Design Spec V1.0
Đọc toàn bộ thư mục `UX_UI_Design_Spec_V1.0/` trước khi triển khai giao diện Web, App tài xế hoặc Tracking khách.

Bộ UX/UI là nguồn sự thật cho: cấu trúc điều hướng, user flow, bố cục màn hình, trạng thái hiển thị, component, design token và tiêu chí nghiệm thu giao diện.

Nếu UX/UI mâu thuẫn với nghiệp vụ V1.1 hoặc hợp đồng kỹ thuật đã khóa, **không được tự đổi nghiệp vụ/API**; phải ưu tiên tài liệu cấp cao hơn và báo lại điểm mâu thuẫn.


# 2. NGUYÊN TẮC BẮT BUỘC

Codex phải tuân thủ các nguyên tắc sau:

### 2.1. Không tự suy đoán nghiệp vụ
Nếu tài liệu không quy định rõ một vấn đề, không tự đặt quy tắc.

Phải:
1. ghi rõ vấn đề chưa đủ thông tin;
2. chỉ ra ảnh hưởng kỹ thuật;
3. đề xuất phương án nếu cần;
4. chờ chủ dự án chốt trước khi triển khai phần đó.

### 2.2. Không tự thay đổi yêu cầu đã khóa
Không được:
- đổi thứ tự ưu tiên tối ưu tuyến;
- đổi bán kính nhận diện điểm giao;
- đổi thời gian hết hạn tracking;
- đổi ngưỡng cảnh báo nhiên liệu;
- đổi khung giờ cảnh báo ngoài giờ;
- thêm yêu cầu ký nhận bắt buộc;
- thêm chức năng khóa/ngắt xe từ xa vào giai đoạn đầu;
- thay đổi state machine nếu chưa được duyệt.

### 2.3. Giữ khả năng truy vết
Mọi chức năng quan trọng phải có khả năng truy ngược:
**Yêu cầu nghiệp vụ → Đặc tả kỹ thuật → API/Database → Source code → Test case.**

Sử dụng `10_MA_TRAN_TRUY_VET.csv` để kiểm soát.

### 2.4. Không code toàn bộ dự án trong một lần
Phải triển khai theo milestone trong `09_KE_HOACH_CODEX.md`.

Sau mỗi milestone:
1. build;
2. chạy test;
3. kiểm tra migration;
4. kiểm tra API;
5. đối chiếu tiêu chí nghiệm thu;
6. báo cáo kết quả;
7. chỉ chuyển milestone tiếp theo khi milestone hiện tại đạt yêu cầu.

---

# 3. CÁC QUYẾT ĐỊNH NGHIỆP VỤ ĐÃ KHÓA

Codex phải xem các quyết định sau là yêu cầu bắt buộc.

## 3.1. Quy mô
- Hiện tại có 1 xe ô tô.
- Kiến trúc phải hỗ trợ tối thiểu 3 xe mà không cần thiết kế lại.
- Hiện có khoảng 5–7 điểm giao/ngày trong TP.HCM.

## 3.2. Nhập đơn
Giai đoạn đầu:
- nhập đơn thủ công trên giao diện;
- hỗ trợ copy/dán nhanh nội dung từ Zalo;
- chưa tích hợp trực tiếp Zalo;
- chưa bắt buộc import Excel.

## 3.3. Điểm đầu và cuối tuyến
- Mặc định xuất phát từ công ty/xưởng;
- mặc định kết thúc tại công ty/xưởng;
- điều phối được phép thay đổi điểm đầu hoặc điểm cuối.

## 3.4. Thời gian hẹn
Phải hỗ trợ:
- giờ cố định;
- khung giờ;
- giao trước một mốc thời gian.

## 3.5. Thứ tự ưu tiên tối ưu tuyến
Bắt buộc theo thứ tự:

1. **Đúng thời gian đã cam kết với khách**
2. **Ít km hơn**
3. **Nhanh hơn**

Không được ưu tiên đường ngắn nếu làm trễ giờ khách.

## 3.6. Nhận diện đến điểm
- Khi xe đi vào bán kính 50 m quanh điểm giao, hệ thống tự động chuyển/đánh dấu trạng thái **Đã đến** theo đặc tả.
- Tài xế và điều phối đều được sửa khi hệ thống nhận sai.
- Mọi lần sửa phải lưu:
  - người sửa;
  - thời gian;
  - trạng thái cũ;
  - trạng thái mới;
  - lý do.

## 3.7. Giao thất bại
Cho phép giao lại.

Luồng:
**Giao không thành công → ghi lý do → chọn ngày/giờ giao lại → đơn quay lại danh sách chờ điều phối.**

## 3.8. Quá tải
- Chỉ cảnh báo.
- Không khóa việc tạo hoặc xuất chuyến.

## 3.9. Bằng chứng giao hàng
Giai đoạn đầu:
- bắt buộc chụp ảnh;
- không bắt buộc chữ ký điện tử;
- ảnh phải gắn với đúng đơn;
- lưu thời gian và tọa độ theo đặc tả.

## 3.10. Tracking khách hàng
- Khách được xem vị trí GPS chính xác của xe.
- Không được xem khách hàng khác.
- Không được xem toàn bộ đội xe.
- Không được xem lịch sử xe ngoài phạm vi đơn của mình.
- Link tracking hết hiệu lực sau **1 giờ kể từ lúc đơn chuyển sang Giao thành công**.
- Giai đoạn đầu hệ thống chỉ tạo link; nhân viên tự gửi qua Zalo.

## 3.11. Nhiên liệu
- Cảnh báo khi chênh lệch giữa nhiên liệu thực tế và mức hệ thống tính vượt **15%**.

## 3.12. Hoạt động ngoài giờ
- Khung giờ cảnh báo: **18:00 đến 07:30 sáng hôm sau**.

## 3.13. Bảo dưỡng
- Chu kỳ bảo dưỡng được cấu hình riêng theo từng xe.

## 3.14. Khóa/ngắt xe từ xa
- Không nằm trong phạm vi giai đoạn đầu.
- Không triển khai SAFE-04 nếu chưa có yêu cầu mới được duyệt.

---

# 4. KIẾN TRÚC KỸ THUẬT MỤC TIÊU

Tuân theo tài liệu kiến trúc đã cung cấp.

Stack dự kiến:

- Backend: FastAPI / Python
- Web điều phối: Next.js + TypeScript
- App tài xế: React Native
- Database: PostgreSQL + PostGIS
- GPS platform: Traccar
- Route optimization: OR-Tools
- Redis: cache / queue / chống xử lý lặp
- Lưu ảnh: S3-compatible private storage / MinIO trong môi trường local
- API: theo `04_OPENAPI.yaml`

Không thay stack chính nếu chưa có lý do kỹ thuật rõ ràng và chưa được duyệt.

---

# 5. QUY TRÌNH TRIỂN KHAI

Triển khai theo milestone đã quy định.

## M0 — Khởi tạo nền tảng
Mục tiêu:
- cấu trúc repository;
- Docker/local environment;
- database;
- migration;
- backend skeleton;
- web skeleton;
- app skeleton;
- CI;
- cấu hình môi trường;
- health check;
- test nền.

Không triển khai nghiệp vụ sâu ở M0.

## M1 — Người dùng, xe, GPS, Traccar

## M2 — Đơn giao, chuyến và trạng thái

## M3 — Tối ưu tuyến

## M4 — App tài xế, offline, geofence

## M5 — Ảnh bằng chứng giao hàng

## M6 — Tracking khách hàng và ETA

## M7 — Nhiên liệu, chi phí, bảo dưỡng, cảnh báo

## M8 — Báo cáo, bảo mật, hiệu năng và nghiệm thu tổng thể

---

# 6. QUY TẮC LÀM VIỆC SAU MỖI MILESTONE

Sau mỗi milestone, Codex phải xuất báo cáo gồm:

### 6.1. Đã triển khai
Liệt kê chức năng và file source chính.

### 6.2. Chưa triển khai
Liệt kê rõ phần còn lại.

### 6.3. Database
- migration nào đã chạy;
- bảng nào mới;
- thay đổi schema nào.

### 6.4. API
Liệt kê endpoint mới và trạng thái.

### 6.5. Test
- test đã chạy;
- số test pass;
- số test fail;
- nguyên nhân fail nếu có.

### 6.6. Sai khác với đặc tả
Nếu có, phải nêu rõ.

### 6.7. Vấn đề cần chủ dự án quyết định
Không được tự xử lý âm thầm.

### 6.8. Hướng dẫn chạy thử
Cung cấp lệnh cụ thể để người kiểm tra chạy lại.

---

# 7. ĐIỀU KIỆN HOÀN THÀNH MỘT MILESTONE

Một milestone chỉ được coi là hoàn tất khi:

- code build thành công;
- migration chạy thành công;
- service khởi động thành công;
- test bắt buộc pass;
- API chính hoạt động;
- không còn lỗi nghiêm trọng;
- đối chiếu yêu cầu nghiệp vụ đạt;
- không có yêu cầu đã khóa bị thay đổi;
- tài liệu kỹ thuật liên quan được cập nhật nếu source thay đổi.

---

# 8. XỬ LÝ MÂU THUẪN TÀI LIỆU

Nếu phát hiện mâu thuẫn:

1. không tự chọn ngẫu nhiên;
2. xác định chính xác file và mục bị mâu thuẫn;
3. áp dụng thứ tự ưu tiên tài liệu tại Phần 1;
4. nếu vẫn không thể kết luận, dừng phần liên quan và báo lại.

Mẫu báo cáo:

> Phát hiện mâu thuẫn giữa [tài liệu A / mục ...] và [tài liệu B / mục ...].  
> Theo thứ tự ưu tiên, tôi đề xuất áp dụng ...  
> Ảnh hưởng: ...  
> Cần xác nhận: Có / Không.

---

# 9. YÊU CẦU VỀ CHẤT LƯỢNG CODE

- Code rõ ràng, dễ bảo trì.
- Không hard-code cấu hình môi trường.
- Không commit secret.
- Có migration database.
- Có validation đầu vào.
- Có xử lý lỗi rõ ràng.
- Có logging.
- Có audit log cho thao tác quan trọng.
- API tuân theo contract đã định nghĩa.
- Mọi thao tác offline đồng bộ lại phải chống tạo dữ liệu trùng.
- Không bỏ qua test chỉ để milestone “xanh”.

---

# 10. YÊU CẦU TRƯỚC KHI BẮT ĐẦU CODE

Sau khi đọc toàn bộ tài liệu, trước khi code Codex phải trả lời ngắn gọn:

1. Đã đọc những tài liệu nào?
2. Kiến trúc hệ thống mà Codex hiểu là gì?
3. Các quy tắc nghiệp vụ cốt lõi là gì?
4. Milestone đầu tiên sẽ làm gì?
5. Có phát hiện mâu thuẫn hoặc thiếu thông tin nào cản trở M0 không?

Nếu không có vấn đề cản trở thì bắt đầu **M0**.

---

# 11. NGUYÊN TẮC CUỐI CÙNG

**Không tối ưu bằng cách làm sai nghiệp vụ.**

**Không tự thêm tính năng ngoài phạm vi.**

**Không tự bỏ tính năng vì cho rằng không cần thiết.**

**Không thay đổi kiến trúc hoặc quy tắc đã khóa mà không báo lại.**

Mục tiêu là xây đúng hệ thống đã được đặc tả, có thể truy vết, kiểm thử và nghiệm thu được.
