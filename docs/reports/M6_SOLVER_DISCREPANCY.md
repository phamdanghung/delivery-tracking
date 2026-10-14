# M6 — Điều tra solver Windows

Cập nhật 14/10/2026; không đổi fixture, solver budget, objectives hoặc business rule.

## Bằng chứng

- Hai focused runs Windows trước DEC-046 bị 422 ngay ở fixture M3 `planned → optimize`; chưa tới assertions tracking. `artifacts/m6-dec045-tests.log`, `m6-dec045-tests-rerun.log`.
- Probe dùng đúng API/tests, database/Redis/OSRM/MinIO thật, chỉ ghi input và CpSolverResponse: original test PASS. Ba phase OPTIMAL, thời gian 0.349/0.024/0.021s; budget ban đầu phase 1 vẫn 1s trong tổng 3s.
- Replay input đó trong một process Windows mới từng phát sinh `NoRoute` ở phase đầu. Lần này chưa ghi được CpSolverResponse trước exception; không được diễn giải thành UNKNOWN hay INFEASIBLE khi chưa có dữ liệu.
- Sau đó Windows replay PASS 5/5 và 15/15 lần trong lúc Docker web đang build; Linux canonical container replay PASS. Cùng input SHA-256 `1b5d7d8e09b37a75b92c6e11b3b45835fa020e9e4c1cef3763fa21633a3b5b9b`, cùng core SHA-256 `995b30273ffe85545909cb75f8dbf681775dc35a0419fd79db8760c196be0c62`, OR-Tools 9.15.6755. Python Windows 3.12.12, Linux 3.12.15.
- Kết quả Windows/Linux giống nhau: order `[4,2,3,1]`, không vi phạm, distance 1567m, elapsed 2607s, cả ba objective được chứng minh OPTIMAL. Solver chạy khoảng 0.235/0.188s trong hai replay đối chiếu.
- `git diff a6438c9 -- apps/api/app/route_optimizer.py` rỗng: core giữ nguyên so với M5 nghiệm thu. Không thay priority, service time, matrix hoặc budget để làm xanh test.
- Original focused M6 sau đó **14 PASS**, không diagnostic wrapper (`artifacts/m6-accepted-risk-tests.log`). Full CI Linux cùng source trước fix BFF **125 +40 PASS**; CI mới kiểm tra lại sau fix.

## Trace tái hiện ngày 14/10/2026

- `m6-solver-cold-20261014.json`: cùng input/core hash trên, OR-Tools trả **UNKNOWN** tại phase 1. Budget vẫn **1.0s**, elapsed đo ngoài native **7.302s**, native wall time **2.110s**, deterministic time **0**, integers/booleans/branches/conflicts đều **0**. Chưa bắt đầu search; không phải INFEASIBLE hoặc MODEL_INVALID.
- Replay tiếp theo vẫn có UNKNOWN trước search khi máy đang chịu tải: elapsed 1.194s, native wall time 0.951s, deterministic time 0 (`m6-solver-warm-20261014.json`). Không gọi nó là warm PASS.
- Host snapshot: available RAM 730MB, pages input 2479/s, page reads 391/s; snapshot sau đó 553MB, pages input 3634/s. OSRM cold startup từ 11:39:31 tới 11:42:29 UTC mới listening; health sau đó tự đạt, OOMKilled false. Đây là bằng chứng môi trường startup/paging chậm, không phải thay đổi source.
- Sau khi stack ổn định, original M6 suite **14 PASS trong 70.96s**, không wrapper, skip hoặc thay thresholds (`m6-oct14-focused-tests.log`). POD/BFF trên canonical và health/head 0008 PASS. Native model/objectives/budget không thay đổi.

## Kết luận

**Discrepancy được giải thích bởi wall-clock budget hết trong khởi tạo/validation native trước search trên host Windows chịu paging/scheduling delay.** Trace UNKNOWN + deterministic time/branches bằng 0 chứng minh lỗi không phải kết luận dữ liệu tuyến bất khả thi. Same-input/core replays OPTIMAL trên Windows/Linux và full CI kiểm chứng không có regression logic M3/M6.

Không khẳng định một page fault cụ thể là nguyên nhân duy nhất; điều đã chứng minh là phase 1 không còn ngân sách search dưới trạng thái môi trường này. Không nới budget/threshold, đổi fixture, warmup tự động hoặc đổi objectives để làm xanh test.

Guard hiện có giữ nguyên: không có complete solution thì NoRoute/HTTP 422, không bỏ stop hoặc duyệt tuyến chưa hợp lệ. Public ETA M6 dùng tuyến đã duyệt + OSRM, không chạy OR-Tools. Không cần đổi contract hoặc thêm workaround. Khi runtime chịu áp lực, cần kiểm tra tài nguyên rồi retry thủ công; không tự phê duyệt production hoặc benchmark production từ bằng chứng local này.

**Không còn blocker solver cho M6.** Required source CI backend 125+40 PASS, local M6 14 PASS; các giới hạn host startup được ghi rõ trong M6_FINAL.md.

Bằng chứng: `m6-solver-probe.log`, `m6-solver-phase-{1,2,3}.json`, `m6-solver-input.json`, `m6-solver-windows-replay*.json`, `m6-solver-linux-replay.json`, `m6-solver-build-replays.log`, `m6-solver-cold-20261014.json`, `m6-solver-warm-20261014.json`, `m6-oct14-focused-tests.log`. Artifacts được ignore; không seed nghiệp vụ vào canonical.
