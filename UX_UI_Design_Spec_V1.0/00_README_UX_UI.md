# UX/UI DESIGN SPEC V1.0 - HỆ THỐNG QUẢN LÝ & ĐỊNH VỊ XE GIAO HÀNG

## 1. Mục đích
Bộ tài liệu này chuyển **nghiệp vụ đã khóa V1.1** và **đặc tả kỹ thuật V1.0** thành chỉ dẫn thiết kế trải nghiệm người dùng và giao diện đủ chi tiết để Codex triển khai frontend nhất quán.

Bộ UX/UI này **không thay đổi nghiệp vụ**. Nếu có mâu thuẫn:
1. Bản nghiệp vụ V1.1 đã khóa là nguồn sự thật cao nhất về nghiệp vụ.
2. Đặc tả kỹ thuật/OPENAPI/Database là nguồn sự thật về hợp đồng kỹ thuật.
3. Bộ UX/UI này là nguồn sự thật về luồng thao tác, bố cục, hành vi giao diện, trạng thái hiển thị và design system.

## 2. Vai trò thiết kế
Góc nhìn: **Senior Product Designer / UX-UI Designer chuyên hệ thống vận hành, logistics, fleet management và dashboard**.

Mục tiêu thiết kế:
- Điều phối nhìn được tình hình trong 5-10 giây.
- Tài xế thao tác ít bước, nút lớn, phù hợp dùng ngoài đường.
- Khách theo dõi đơn cực đơn giản, không thấy dữ liệu nội bộ.
- Hệ thống có trạng thái rõ ràng khi mất mạng, GPS cũ, giao trễ, quá tải, lỗi đồng bộ.
- Giao diện nhất quán để Codex không tự sáng tác từng màn hình.

## 3. Phạm vi
### Web Điều phối/Quản trị
14 màn hình chính.

### App tài xế
8 màn hình/chức năng chính.

### Tracking khách
3 trạng thái giao diện chính.

## 4. File trong bộ này
1. `01_KIEN_TRUC_THONG_TIN.md`
2. `02_USER_FLOWS.md`
3. `03_WIREFRAME_SPEC.md`
4. `04_DESIGN_SYSTEM.md`
5. `05_SCREEN_BY_SCREEN_SPEC.md`
6. `06_UI_UX_ACCEPTANCE_TESTS.md`

## 5. Quy tắc cho Codex
- Không tự đổi luồng nghiệp vụ.
- Không tự thêm nút/chức năng có tác động nghiệp vụ nếu không có trong đặc tả.
- Dùng component tái sử dụng; không copy/paste UI rời rạc.
- Mọi trạng thái `loading / empty / error / offline / stale GPS / disabled` phải có thiết kế.
- Không dùng màu sắc là tín hiệu duy nhất; luôn có chữ/icon đi kèm.
- Web ưu tiên desktop; app tài xế và tracking khách ưu tiên mobile.
