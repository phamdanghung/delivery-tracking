# M8 — Rà soát accepted risks M0–M7

Ngày review: **16/10/2026**. Đây là rà soát, không phải quyết định phê duyệt rủi ro mới.

| Milestone | Quyết định | Phạm vi đã được phê duyệt | Còn áp dụng cho M8 / production? |
|---|---|---|---|
| M0 | DEC-023 | Hai advisory, M0 development/local/CI | Không / Không |
| M1 | DEC-024 | Hai advisory, M1 development/local/CI | Không / Không |
| M2 | DEC-029 | Hai advisory, M2 development/local/CI | Không / Không |
| M3 | DEC-033 | Hai advisory, M3 development/local/CI | Không / Không |
| M4 | DEC-035 | Hai advisory, M4 development/local/CI | Không / Không |
| M5 | DEC-040 | Hai advisory, M5 development/local/CI | Không / Không |
| M6 | DEC-046 | Hai advisory, M6 development/local/CI | Không / Không |
| M7 | DEC-050 | Hai advisory, M7 development/local/CI | Không / Không |

Hai advisory chung:

- [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): affected <=3.0.3, upstream ghi patched versions **None** tại ngày review.
- [node-forge GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv): affected <=1.4.0, upstream ghi patched versions **None** tại ngày review.

Raw npm audit đầu M8: **21 high affected-package findings**, từ hai advisory gốc; không phải 21 advisory độc lập. Bằng chứng `artifacts/m8-npm-audit-initial.json`; phân loại và dependency paths tham chiếu [M0_DEPENDENCY_SECURITY.md](M0_DEPENDENCY_SECURITY.md). Không sửa lockfiles/Expo/React Native hoặc coi advisory đã vá.

M7 web traces/native maps không tham chiếu packages advisory; đó là bằng chứng M7, không thay cho việc kiểm tra artifact/image M8 sau thay đổi. Tooling vẫn có trên build/dev/CI và web image cũ chứa toàn bộ workspace node_modules. M8 giảm runtime image bằng standalone; phải xác minh lại trước khi kết luận, không dùng việc giảm image để ẩn raw audit.

## Các điều kiện vẫn phải giữ

- Chỉ repo/config/cert tin cậy; Metro/Compose chỉ phạm vi cần thiết/loopback.
- Không `npm audit fix --force`; không downgrade Expo/React Native chỉ để audit về 0; không suppress/ẩn advisory; giữ raw audit và runtime-surface gates.
- Review muộn nhất **02/11/2026 hoặc trước production**, mốc nào đến trước. Có patch upstream: ưu tiên nâng cấp/chạy lại đầy đủ kiểm tra liên quan. Có runtime exposure thực tế: dừng phần liên quan, đánh giá lại ngay.
- Không tự gia hạn/phê duyệt M8 hoặc production. Nếu còn advisory khi chốt M8 thì báo chủ dự án với attack-surface evidence và rủi ro thực tế.

## Các giới hạn trước đây phải xem lại ở final acceptance

- UI trực quan/native device E2E/GPS ngoài đường chưa được nghiệm thu đầy đủ; M7 đã ghi rõ Computer Use bị dừng. Không đổi các ô này thành PASS chỉ vì API/build/CI đạt.
- Cold startup/paging của host từng làm readiness và bài solver M3 không đạt. Sau ổn định đã có full local/CI PASS; không nới mục tiêu 5 giây hoặc đổi objective. Production cần đo trên môi trường tương ứng.
- Legacy database/runtime chưa phục hồi; giữ PRESERVED, không production data. DEC-041 khóa canonical `fleet-delivery-dev`; việc test restore vào đích mới không thay canonical.
- Harsh braking/out-of-area chưa được bật do thiếu contract/nguồn/ngưỡng theo DEC-048; remote immobilization bị loại theo DEC-021. Không tự mở rộng để “đủ” acceptance.
- Production TLS, least-privilege DB/storage, secrets lifecycle, backup offsite/PITR/retention/scheduling, load/UAT và vận hành on-call cần bằng chứng riêng. Không có DEC accepted-risk nào ở trên miễn trừ các kiểm soát đó.
