# M8 acceptance matrix

Source M8 `9d5afd3fd290256ae01210918181af9e313926e3`; [CI thực tế 38979648260](https://github.com/phamdanghung/delivery-tracking/actions/runs/38979648260): backend 267 PASS, round-trip migration rồi 60 integration PASS; frontend 10 + 12 tests/build/export/runtime gates PASS, raw npm audit FAIL. Các ô PASS dưới đây là tự động, không thay UI/UAT, thiết bị thật hoặc production acceptance.

| Mục Technical Pack 08 | Bằng chứng tự động hiện có | Giới hạn / M8 |
|---|---|---|
| AT-01 GPS trực tiếp | M1 ingest + real Traccar trong regression M8 | M8 CI **PASS**; thiết bị thật/UI/end-to-end 5–15s chưa xác minh |
| AT-02 GPS stale/lost | `test_gps.py`, M6 stale/invalid ETA | M8 CI **PASS** |
| AT-03 7 đơn/3 kiểu hẹn | M2 `test_seven_orders_three_commitments_draft_overload_and_no_approval` | M8 CI **PASS**; hành vi draft tham chiếu DEC M2/M3 |
| AT-04 Ưu tiên đúng hẹn | core routing + M3 real OSRM/infeasible/approval tests | M8 CI **PASS**; không đổi objective/threshold |
| AT-05 Geofence một lần | M4 PostGIS hysteresis/offline replay | M8 CI **PASS**; không thay bằng ảnh minh họa/UI |
| AT-06 Sửa ARRIVED/audit | M4 correction reason/50–70m/replay | M8 CI **PASS** |
| AT-07 POD gate | M5 real private upload/one DELIVERED event | M8 CI **PASS** |
| AT-08 Offline POD | M4/M5 mobile queue + API idempotency/private upload | M8 CI **PASS**; airplane-mode/restart trên thiết bị thật chưa xác minh |
| AT-09 Giao lại | M2 failed/proposal/requeue; M5 new-attempt POD | M8 CI **PASS** |
| AT-10 Tracking privacy | M6 scoped token/RBAC/GPS/no internal data | M8 CI **PASS**; GPS ẩn sau giao theo DEC M6 |
| AT-11 +1 giờ 410 | M6 exact expiry/new-attempt/revoke | M8 CI **PASS** |
| AT-12 Quá tải warning | M2 draft + M3 approval/3 vehicles | M8 CI **PASS** |
| AT-13 ABS variance >15% | M7 fuel math + real Traccar reconciliation | M8 CI **PASS**; không dùng km kế hoạch |
| AT-14 Ngoài giờ | M7 safety boundaries/activity/exception/incident | M8 CI **PASS** |
| AT-15 Bảo dưỡng từng xe | M7 maintenance rules/events/km/day/source tests | M8 CI **PASS** |
| AT-16 Không remote immobilization | Contract/source review baseline | M8 rà soát cuối chờ |
| WEB-13 Reporting | DEC-051–055; GET/Admin, KPI theo attempt, telemetry thực, tài chính tách nguồn | **PASS tự động**: 37 policy/telemetry tests, 5 DB/API tests trong CI; local Windows reporting/contract13 PASS; BFF regression PASS; UI trực quan chưa xác minh |
| M8 API hardening/logging | Targeted hardening/backup guard/redaction và full regression | **PASS tự động** trong CI M8; production ingress/log delivery chưa xác minh |
| M8 DB/POD/Traccar restore | Canonical bundle restore PASS: head0009, 70 fingerprint, cleanup; CI drill có POD/GPS thật | **PASS local/CI**: 1 ảnh private/version gốc/signed read/anonymous403, 1 GPS device/position; không phải production rehearsal/RTO |
| M8 canonical runtime | Engine29.7.2 và 7 service healthy với image M8; head0009, legacy giữ nguyên | **PASS canonical**: PostGIS3.5.2/head0009; live/ready; Redis; MinIO private/versioning; Traccar/OSRM; bootstrap/login/BFF reporting; business tables0. IPC workaround và local DB incident chưa có root-cause fix triệt để |
| M8 performance | M3 strict5s/M6 cached tracking p95<1s trong regression M8 PASS | 3 warm read API p95 **5.279/6.804/7.815ms**, 10 mẫu/route trên DB rỗng; historical readiness p95 **1103ms**. Production load/GPS end-to-end chưa xác minh |
| M8 security audit | npm21high/2 advisory chưa vá; Python lock audit0 findings | **FAIL raw npm audit**; DEC-056 chấp nhận riêng M8 development/local/CI, chưa vá và không áp dụng production |
| UI / device UAT / final owner acceptance | Chưa có bằng chứng hoàn tất | **CHƯA XÁC MINH** |
| Production readiness | Review cấu hình local cho thấy blockers | **CHƯA ĐẠT**; xem `../operations/PRODUCTION_READINESS.md` |

Kết luận M8 **PASS WITH CONDITIONS** chỉ cho development/local/CI theo bằng chứng và DEC-056. Các mục UAT/chưa xác minh/production chưa đạt trong bảng giữ nguyên; raw audit/frontend job/workflow vẫn FAIL.

Không dùng PASS của một dòng để thay thế bằng chứng của dòng khác. Chi tiết trạng thái/run/commit trong [M8_FINAL.md](M8_FINAL.md).
