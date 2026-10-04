# 03 - WIREFRAME SPEC

Các sơ đồ dưới đây là wireframe logic; Codex phải bám cấu trúc, có thể tinh chỉnh khoảng cách theo design system nhưng không tự đổi luồng.

## WEB-02 - Bảng điều khiển hôm nay
```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Sidebar │ HÔM NAY 04/10/2026        Tìm kiếm...       GPS ●   🔔   User   │
├─────────┼───────────────────────────────────────────────────────────────────┤
│         │ [Đơn: 7] [Đã giao: 3] [Đang giao: 2] [Nguy cơ trễ: 1]          │
│         │                                                                   │
│         │ ┌──────────────────── BẢN ĐỒ XE TRỰC TIẾP ────────────────────┐  │
│         │ │  marker xe + trạng thái + điểm đang phục vụ                 │  │
│         │ └─────────────────────────────────────────────────────────────┘  │
│         │                                                                   │
│         │ CẦN XỬ LÝ NGAY                                                    │
│         │ [⚠ Đơn DH123 nguy cơ trễ 18 phút] [⚠ Xe 51C... GPS cũ 4 phút]    │
│         │                                                                   │
│         │ TIẾN ĐỘ CHUYẾN HÔM NAY                                            │
│         │ Điểm | Khách | Cam kết | ETA | Trạng thái | Hành động           │
└─────────┴───────────────────────────────────────────────────────────────────┘
```

## WEB-05 - Tạo đơn
```text
┌───────────────────────────────────────────────────────────────┐
│ TẠO ĐƠN GIAO HÀNG                                             │
│                                                               │
│ [DÁN NỘI DUNG ZALO]                                           │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ nội dung thô...                                           │ │
│ └───────────────────────────────────────────────────────────┘ │
│ [Tách thông tin]                                              │
│                                                               │
│ Khách hàng*      [________________________]                    │
│ SĐT*             [________________________]                    │
│ Địa chỉ*         [________________________] [Kiểm tra bản đồ]  │
│ Kiểu hẹn*        (• Khung giờ ○ Giờ cố định ○ Trước mốc)     │
│ Thời gian        [________] [________]                         │
│ Khối lượng       [____ kg]   Thể tích [____ m³]               │
│ Ghi chú          [________________________]                    │
│                                                               │
│                                [Hủy] [Lưu đơn]                 │
└───────────────────────────────────────────────────────────────┘
```

## WEB-07 - Duyệt tuyến tối ưu
```text
┌──────────────────────────────────────────────────────────────────────┐
│ CHUYẾN 04/10 - XE 51C-xxxxx               [Tối ưu lại] [Duyệt chuyến]│
├──────────────────────────────────────────────────────────────────────┤
│ BẢN ĐỒ 65%                                  TÓM TẮT 35%              │
│                                              7 điểm                   │
│ ① Xưởng                                     43.2 km                  │
│ ② Khách A  09:00-10:00                     3h12                     │
│ ③ Khách B  trước 11:30                     Nguy cơ trễ: 1           │
│ ...                                          Cảnh báo tải: Không      │
│                                                                      │
│                                             THỨ TỰ ĐIỂM              │
│                                             drag handle + ETA        │
│                                             badge đúng giờ/trễ       │
└──────────────────────────────────────────────────────────────────────┘
```

## DRV-02 - Chuyến hôm nay
```text
┌──────────────────────────────┐
│ HÔM NAY          ● Đã đồng bộ│
│ 5/7 điểm                     │
│                              │
│ TIẾP THEO                    │
│ ┌──────────────────────────┐ │
│ │ Khách B                  │ │
│ │ Trước 11:30              │ │
│ │ ETA 10:48  ✓ Đúng giờ   │ │
│ │ 3.2 km                   │ │
│ │ [MỞ CHỈ ĐƯỜNG]           │ │
│ └──────────────────────────┘ │
│                              │
│ ① ✓ Khách A - Đã giao       │
│ ② ● Khách B - Đang đi       │
│ ③ ○ Khách C - 13:00-14:00   │
│ ...                          │
│                              │
│ Hôm nay | Chi phí | Tài khoản│
└──────────────────────────────┘
```

## DRV-03 - Chi tiết điểm giao
```text
┌──────────────────────────────┐
│ ← KHÁCH B                    │
│ Đang đi giao                 │
│                              │
│ Trước 11:30                  │
│ ETA 10:48  ✓                 │
│                              │
│ Nguyễn Văn A                 │
│ 09xx xxx xxx   [Gọi]         │
│ 123 ... TP.HCM               │
│ [MỞ GOOGLE MAPS]             │
│                              │
│ Ghi chú: nhận tại kho sau    │
│                              │
│ [BẮT ĐẦU BÀN GIAO]           │
│                              │
│ Giao thất bại                │
└──────────────────────────────┘
```

## DRV-05 - Chụp ảnh POD
```text
┌──────────────────────────────┐
│ ẢNH BẰNG CHỨNG              │
│                              │
│ [      CAMERA / PREVIEW    ] │
│                              │
│ 1 ảnh đã chụp                │
│ Thời gian: 10:52             │
│ GPS: Đã ghi nhận             │
│                              │
│ [+ Chụp thêm]                │
│                              │
│ [GIAO THÀNH CÔNG]            │
└──────────────────────────────┘
```

## CUS-01 - Tracking khách
```text
┌──────────────────────────────┐
│ ĐƠN HÀNG ĐANG ĐƯỢC GIAO     │
│ ETA khoảng 18 phút           │
│ Cập nhật GPS: 10:42:16       │
│                              │
│ ┌──────────────────────────┐ │
│ │        BẢN ĐỒ           │ │
│ │        🚚 vị trí xe      │ │
│ └──────────────────────────┘ │
│                              │
│ Trạng thái: Đang đi giao     │
│                              │
│ Mã đơn: DH12345              │
└──────────────────────────────┘
```

## Trạng thái giao diện bắt buộc
Mỗi màn hình dữ liệu phải thiết kế đủ:
- Loading skeleton.
- Empty state có hướng dẫn hành động.
- Error state có nút thử lại.
- Permission denied.
- Offline (app tài xế).
- GPS stale/mất tín hiệu.
- Disabled/processing cho nút gửi để chống bấm lặp.
