# M8 acceptance matrix

Trạng thái đang xác minh; không phải nghiệm thu cuối. Baseline M7: `3cefe37fb8c9a334ed98579389662841202d6808`. Các test M0–M7 dưới đây đã có bằng chứng M7; phải ghi thêm run M8 sau khi source M8 hoàn chỉnh.

| Mục Technical Pack 08 | Bằng chứng tự động hiện có | Giới hạn / M8 |
|---|---|---|
| AT-01 GPS trực tiếp | M1 ingest + real Traccar M7 | M8 regression chờ; thiết bị thật/UI/end-to-end 5–15s chưa xác minh |
| AT-02 GPS stale/lost | `test_gps.py`, M6 stale/invalid ETA | M8 regression chờ |
| AT-03 7 đơn/3 kiểu hẹn | M2 `test_seven_orders_three_commitments_draft_overload_and_no_approval` | M8 regression chờ; hành vi draft tham chiếu DEC M2/M3 |
| AT-04 Ưu tiên đúng hẹn | core routing + M3 real OSRM/infeasible/approval tests | M8 regression chờ; không đổi objective/threshold |
| AT-05 Geofence một lần | M4 PostGIS hysteresis/offline replay | M8 regression chờ; không thay bằng ảnh minh họa/UI |
| AT-06 Sửa ARRIVED/audit | M4 correction reason/50–70m/replay | M8 regression chờ |
| AT-07 POD gate | M5 real private upload/one DELIVERED event | M8 regression chờ |
| AT-08 Offline POD | M4/M5 mobile queue + API idempotency/private upload | M8 regression chờ; airplane-mode/restart trên thiết bị thật chưa xác minh |
| AT-09 Giao lại | M2 failed/proposal/requeue; M5 new-attempt POD | M8 regression chờ |
| AT-10 Tracking privacy | M6 scoped token/RBAC/GPS/no internal data | M8 regression chờ; GPS ẩn sau giao theo DEC M6 |
| AT-11 +1 giờ 410 | M6 exact expiry/new-attempt/revoke | M8 regression chờ |
| AT-12 Quá tải warning | M2 draft + M3 approval/3 vehicles | M8 regression chờ |
| AT-13 ABS variance >15% | M7 fuel math + real Traccar reconciliation | M8 regression chờ; không dùng km kế hoạch |
| AT-14 Ngoài giờ | M7 safety boundaries/activity/exception/incident | M8 regression chờ |
| AT-15 Bảo dưỡng từng xe | M7 maintenance rules/events/km/day/source tests | M8 regression chờ |
| AT-16 Không remote immobilization | Contract/source review baseline | M8 rà soát cuối chờ |
| WEB-13 Reporting | DEC-051–055 đã chốt; API GET/Admin, KPI EARLY/ON_TIME/LATE/UNKNOWN, telemetry thực và tài chính tách nguồn đang triển khai | 25 policy tests PASS; DB/BFF/build/CI mới đang xác minh |
| M8 API hardening/logging | 33 targeted tests PASS (`artifacts/m8-hardening-focused.log`) | Full regression/CI M8 chờ |
| M8 DB/POD/Traccar restore | Canonical bundle restore vào target cô lập PASS: head0009, 70 fingerprint bảng khớp, cleanup PASS | Canonical không có ảnh/GPS; CI drill ảnh/version/GPS phải chạy lại sau sửa template0 |
| M8 canonical runtime | Engine29.7.2 khôi phục lại 17/10; 7 service healthy, source volumes giữ nguyên | Chưa deploy reporting image mới; phải xác minh cuối |
| M8 performance | M3 strict5s/M6 cached tracking p95<1s baseline | M8 regression + common API đo thực chờ; production load chưa xác minh |
| M8 security audit | npm21high/2 advisory chưa vá; Python lock audit0 findings | M8 chưa có accepted-risk DEC; production không được chấp nhận theo DEC cũ |
| UI / device UAT / final owner acceptance | Chưa có bằng chứng hoàn tất | **CHƯA XÁC MINH** |
| Production readiness | Review cấu hình local cho thấy blockers | **CHƯA ĐẠT**; xem `../operations/PRODUCTION_READINESS.md` |

Không dùng PASS của một dòng để thay thế bằng chứng của dòng khác. Chi tiết trạng thái cuối/run/commit sẽ được ghi trong `M8_FINAL.md`.
