# Project development summary

Ngày đóng development: **17/10/2026**. Phạm vi: development/local/CI; không phải nghiệm thu production.

## Trạng thái M0–M8

| Milestone | Phạm vi | Trạng thái nghiệm thu | DEC accepted risk |
|---|---|---|---|
| M0 | Nền tảng, Docker, database, CI | PASS WITH ACCEPTED RISK | DEC-023 |
| M1 | Người dùng, xe, GPS, Traccar | PASS WITH ACCEPTED RISK | DEC-024 |
| M2 | Đơn, chuyến, trạng thái | PASS WITH ACCEPTED RISK | DEC-029 |
| M3 | Tối ưu tuyến OR-Tools | PASS WITH ACCEPTED RISK | DEC-033 |
| M4 | Driver App, offline, geofence, audit | PASS WITH ACCEPTED RISK | DEC-035 |
| M5 | e-POD ảnh/private storage | PASS WITH ACCEPTED RISK | DEC-040 |
| M6 | Tracking theo token/lượt giao, ETA | PASS WITH ACCEPTED RISK | DEC-046 |
| M7 | Fuel, expenses, maintenance, safety | PASS WITH ACCEPTED RISK | DEC-050 |
| M8 | Reporting, hardening, recovery, acceptance review | **PASS WITH CONDITIONS** | DEC-056 |

Báo cáo FINAL từng milestone giữ nguyên lịch sử; M0 dùng [M0_FINAL_REVISION.md](M0_FINAL_REVISION.md). Bằng chứng và điều kiện hiện hành: [M8_FINAL.md](M8_FINAL.md), [acceptance matrix](M8_ACCEPTANCE_MATRIX.md).

## Đóng Git và các quyết định chính

- [PR #7](https://github.com/phamdanghung/delivery-tracking/pull/7): 8 commits/42 files so với M7, chỉ phạm vi M8 đã nghiệm thu; merge commit **c814d1f3d6a34074c4c39ab49e32625ad0d5fa6e**. Nhánh chuẩn **codex/m0-foundation** đã đồng bộ sau merge; tài liệu này được bổ sung sau merge. Không deploy production.
- [PROJECT_DECISIONS.md](../../PROJECT_DECISIONS.md): DEC-034/036 khóa correction ARRIVED và offline conflict; DEC-037–039 khóa GPS/nguồn ảnh/POD theo lượt; DEC-042–045 khóa tracking lifecycle, cấp/thu hồi link, privacy và ETA; DEC-047–049 khóa fuel, safety, quyền và maintenance.
- DEC-041 khóa canonical runtime; DEC-051–055 khóa reporting ADMIN-only, ARRIVED theo attempt, EARLY/ON_TIME/LATE/UNKNOWN, telemetry thực và chống double-count. DEC-056 chỉ chấp nhận hai advisory M8 development/local/CI; không miễn trừ UAT hoặc production blockers.

## Database và runtime

- Migration hiện tại **0009** (chuỗi 0001–0009); M8 không thêm/sửa migration lịch sử.
- Canonical development runtime: **fleet-delivery-dev** theo DEC-041; dùng database/volumes riêng. Bằng chứng cuối M8: 7 service chính healthy, MinIO private/versioning, API live/ready và admin-web PASS; chỉ bootstrap ADMIN, không seed dữ liệu nghiệp vụ giả.
- Stack/runtime/volumes cũ vẫn **PRESERVED/LEGACY**, chưa phục hồi database cũ; không reset/prune/xóa/ghi đè, không coi là production data. Lượt đóng Git này không thay đổi runtime và không chạy lại health; tham chiếu bằng chứng M8_FINAL.

## Accepted risks còn mở và CI

- **braces GHSA-vfj7-8cjw-p6xm** và **node-forge GHSA-86w9-cpqp-85rv** vẫn chưa vá; các DEC M0–M8 chỉ áp dụng riêng milestone tương ứng trong development/local/CI, không áp dụng production.
- Giữ repo/config/cert đáng tin cậy, Metro/Compose trong phạm vi cần thiết/loopback; không force fix, downgrade Expo/React Native hoặc suppress advisory; tiếp tục raw audit và runtime-surface gates.
- Review muộn nhất **02/11/2026 hoặc trước production**, mốc nào đến trước. Có patch upstream phải ưu tiên nâng cấp/kiểm tra lại; có runtime exposure phải dừng phần liên quan và đánh giá lại ngay.
- [CI final head trước merge 39029848129](https://github.com/phamdanghung/delivery-tracking/actions/runs/39029848129): backend PASS; frontend test/build/Android+iOS export/runtime gates PASS; **raw npm audit FAIL, frontend job FAIL, workflow FAIL** theo ngoại lệ DEC-056. Không đổi kết quả này thành CI PASS. [CI source và số liệu regression](https://github.com/phamdanghung/delivery-tracking/actions/runs/38979648260): 267 backend tests và 60 integration tests sau migration round-trip PASS. CI sau merge là run riêng, không được suy ra PASS từ bằng chứng trước merge.

## Production blockers và nghiệm thu còn thiếu

Giữ nguyên toàn bộ mục 5–8 của M8_FINAL và các ô chưa xác minh trong acceptance matrix:

- Hai advisory chưa vá vẫn chặn production; scan OS/base image/native binary/vendored code chưa đầy đủ.
- Deployment target/staging, domain/TLS/firewall, secrets rotation, DB/storage least privilege và hạn quyền sửa audit chưa được kiểm chứng; local DB role quyền cao/kết nối không TLS.
- Backup production encrypted/offsite/immutable, scheduler/PITR/retention, RPO/RTO được duyệt và restore rehearsal trên hạ tầng đích chưa hoàn tất.
- UI trực quan/UAT, Android/iOS thiết bị thật, offline/reconnect/geofence, GPS ngoài đường/end-to-end 5–15s, tải/soak đại diện, pilot và nghiệm thu production cuối của chủ dự án chưa hoàn tất. Việc chủ dự án nghiệm thu milestone có điều kiện không thay các bằng chứng này.
- Log/alert routing/on-call và outbox observability chưa đầy đủ; local Docker Desktop IPC workaround và sự cố PostgreSQL worker/recovery chưa có root-cause fix triệt để. Các giới hạn đo hiệu năng trên database rỗng vẫn giữ nguyên.
- Reporting ngoài WEB-13 thiếu contract tiếp tục deferred; không mở rộng nghiệp vụ hoặc triển khai remote immobilization.

## Kết luận

**Development complete / Production acceptance incomplete.**

M8 đóng ở **PASS WITH CONDITIONS** theo nghiệm thu của chủ dự án và DEC-056. **Chưa production-ready**; không chuyển thành PASS vô điều kiện, không deploy production.
