# M0 FINAL REVISION

Ngày: 2026-10-04. Tiếp tục M0 từ nền tảng hiện có; không chuyển M1. Báo cáo này thay trạng thái hiện tại của M0_FINAL.md, giữ báo cáo cũ làm lịch sử.

## 1. Dependency tree và phân loại từng nhóm advisory

Đã phân tích đủ 26 affected-package entries ban đầu, từ 3 advisory gốc. Bảng từng package và toàn bộ đường dependency nằm trong [M0_DEPENDENCY_SECURITY.md](M0_DEPENDENCY_SECURITY.md): braces 20 đường, node-forge 2 đường, uuid 10 đường. Số finding không phải số CVE độc lập.

- Runtime package: expo, react-native, virtualized-lists; advisory lan truyền từ tooling. @expo/cli có module-loader runtime được Expo nhúng, nhưng các primitive glob/crypto có advisory không được nhúng.
- Build/dev/tooling: 23 package có vai trò tooling, gồm CLI/config/Metro/Xcode, lint/fast-glob/micromatch, braces, forge, uuid. CLI có vai trò hỗn hợp như trên.
- Transitive: 23 package; dependency trực tiếp là expo, react-native và eslint-config-next (dev). Transitive là quan hệ dependency, có thể đồng thời thuộc runtime hoặc tooling.

Ví dụ đường đầy đủ:

```text
@fleet/admin-web → eslint-config-next@16.3.8 → @next/eslint-plugin-next@16.3.8
  → fast-glob@3.3.1 → micromatch@4.0.8 → braces@3.0.3
@fleet/driver-mobile → expo@57.0.26 → @expo/cli@57.0.27 → node-forge@1.4.0
@fleet/driver-mobile → expo@57.0.26 → @expo/cli@57.0.27
  → @expo/code-signing-certificates@0.0.6 → node-forge@1.4.0
@fleet/driver-mobile → expo@57.0.26 → @expo/config-plugins@57.0.9
  → xcode@3.0.1 → uuid@7.0.3 (trước) / uuid@11.1.1 (sau)
```

## 2. Advisory nào đã xử lý

[UUID GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq) được xử lý bằng root override chỉ cho xcode: uuid 11.1.1, vẫn hỗ trợ CommonJS. Loại 7 moderate entries. xcode sử dụng v4(); test mới xác minh tạo 1.000 ID đúng định dạng/không trùng và v5 từ chối buffer ngắn trước khi ghi.

Không audit force, downgrade Expo, ignore/suppress hoặc mock kiểm tra.

## 3. Advisory nào chưa thể xử lý và lý do

- [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): <=3.0.3, chưa có bản vá. Pattern glob lồng sâu có thể làm dừng tooling. Cha micromatch/fast-glob hiện chưa loại dependency này trong stack tương thích.
- [node-forge GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv): <=1.4.0, chưa có bản vá. Rủi ro xác minh chữ ký RSA trong tooling ký/chứng chỉ. Expo CLI/certificates phiên bản tương thích vẫn dùng forge, kể cả certificates 0.0.7.

Không có bản thay thế drop-in đã chứng minh tương thích; không tự sửa parser hoặc crypto. Audit vẫn công khai mức high. Đánh giá attack surface có phạm vi M0: không thấy primitive dễ bị tấn công trong runtime web/mobile đã build. Rủi ro tooling vẫn còn khi xử lý config/glob/cert không tin cậy. Chi tiết bằng chứng và phương án ở báo cáo bảo mật.

## 4. Các dependency/file đã thay đổi

Revision này:

- package.json/package-lock.json: override UUID 7.0.3 → 11.1.1; pin npm 12.2.0 và Node tương thích. Khi tái tạo lock, regenerate 1.4.2 → 1.5.0 (Babel tooling); các phiên bản package khác giữ nguyên. Expo 57.0.26, RN 0.86.3, React và Next không đổi.
- infra/docker/web.Dockerfile, .github/workflows/ci.yml, scripts/verify.ps1: npm 12.2.0 cho môi trường riêng; uv script ngoài thư mục API dùng --project . rõ ràng; CI thêm kiểm tra runtime source map.
- apps/driver-mobile/package.json: export Android/iOS với hai worker/source maps; Metro mặc định localhost. Không thêm thư mục native hoặc chức năng nghiệp vụ.
- packages/shared/tests/dependency-security.test.mjs: 2 test regression tương thích/bounds.
- scripts/analyze_dependencies.mjs, scripts/verify_mobile_surface.mjs: dependency graph và kiểm tra bundle thật.
- README.md và docs/reports/M0_DEPENDENCY_SECURITY.md, M0_FINAL_REVISION.md: hướng dẫn, đánh giá và kết quả.

Các thay đổi M0 trước revision, được đưa lên remote cùng nhánh: Compose/.env.example/MinIO-mc Dockerfiles; migration ENV/tests config/database; scripts dev/database/stack verification; shared design tokens, web/mobile skeleton styles; ADR/traceability/reports; bộ START_HERE V1.1 và UX/UI do chủ dự án bổ sung. Chi tiết file tại mục 8 của M0_FINAL.md và lịch sử Git. SQL/OpenAPI baseline nguyên vẹn, test byte-for-byte PASS. .env/secrets/node_modules/venv/artifacts không commit.

## 5. Kết quả npm ci

PASS với npm 12.2.0, local Node 24.15.0; cài sạch 761 packages. npm ls --all exit 0, UUID 11.1.1 được đánh dấu overridden, không invalid dependency. Docker/CI dùng npm cùng phiên bản. CI Linux cài sạch 762 packages (khác optional platform binding).

npm 11 có lỗi override/workspaces [npm/cli#9514](https://github.com/npm/cli/issues/9514); không đổi npm global của máy người dùng. npm 12 có cảnh báo postinstall unrs-resolver chưa nằm trong allowScripts mặc định; platform binding đã có, lint/build thực tế đạt. Không tắt cảnh báo hoặc test.

## 6. Kết quả npm audit

Trước: 26 = 19 high + 7 moderate. Sau: **19 high, 0 moderate, 0 critical**; hai advisory gốc chưa vá. Audit exit 1 đúng do findings còn tồn tại; **không ghi audit PASS**. JSON đầy đủ local: artifacts/m0-revision-audit-before.json và m0-revision-audit-after.json. Không dùng --omit để che tooling.

## 7. Kết quả build web

PASS local Windows Node 24 và Docker Node 22.23.3; Next.js 16.3.8 build production các route skeleton / và /_not-found. Lint và typecheck workspace PASS. Năm trace server *.nft.json sau build không tham chiếu braces/forge/uuid/xcode/micromatch. Tooling vẫn có trong Docker node_modules; không tuyên bố đã xóa khỏi image.

## 8. Kết quả Expo Android/iOS export

PASS với Expo SDK 57/RN 0.86.3, Hermes bundles Android ~1.2 MB và iOS ~1.1 MB. Source maps thực tế: Android 578 sources, iOS 580 sources; không có braces, forge, uuid, xcode, micromatch hoặc certificates.

Cả hai chứa Expo CLI metro-require/require.js làm runtime module-loader. Đã đọc source và phân loại riêng; không import primitive có advisory. CI đầu tiên phát hiện phép kiểm tra quá rộng; sửa dựa trên source và chạy lại, vẫn kiểm tra đầy đủ package dễ bị tấn công. Không coi export là native APK/IPA hay kiểm thử thiết bị.

## 9. Kết quả backend/database test

PASS: 11 backend tests, 0 fail, 0 skip, gồm đủ 2 integration database tests. Dev PostGIS thật revision 0001; database test riêng được tạo, migrate, full pytest, downgrade base/upgrade head, chạy lại 2 database tests và xóa đúng database test. Không downgrade database vận hành.

Node: 3 PASS, 0 fail/skip. Tổng **14 test độc lập** (11 backend + 3 Node); 2 test DB lặp sau round trip không cộng thành test độc lập. Ruff check/format 11 files, mypy 4 files PASS. Warning Starlette/httpx vẫn hiển thị.

## 10. Trạng thái Docker/stack/health sau thay đổi

**PASS** sau build/recreate web container mới; Engine 29.7.2, npm trong container 12.2.0, UUID 11.1.1 overridden. docker compose up --no-build --wait exit 0. Xác minh lại lúc 2026-10-04 22:32:29 +07:00.

| Service | Trạng thái |
|---|---|
| postgres (PostGIS 16/3.5) | Healthy |
| redis | Healthy |
| minio | Healthy |
| minio-init | Exited 0, đúng one-shot |
| traccar | Healthy |
| api | Healthy |
| admin-web (image mới) | Healthy |

Health thật: API live/ready 200, bốn dependency checks true; web 200/lang vi; Traccar /api/server 200; Redis PONG; MinIO private bucket versioning Enabled, signed write/read PASS, anonymous GET 403. Đã xóa đúng version object test vừa tạo. Trong container web mới: 5 server traces, 0 reference package gốc advisory. Không reset Docker/xóa volume hoặc sửa container dự án khác.

## 11. Trạng thái CI remote

origin: https://github.com/phamdanghung/delivery-tracking.git. Nhánh codex/m0-foundation đã push; không tạo repository mới, không force push.

Run 37213071173, source SHA 2d589719fb953f4f43cfd4644e3396cb772c90ed: frontend/backend đều SUCCESS, đã tải log jobs 111467984577/111467984692. [Run thực tế](https://github.com/phamdanghung/delivery-tracking/actions/runs/37213071173).

Frontend xác minh npm ci/lint/typecheck/3 Node tests/web build/Android+iOS export/source maps. Backend dùng PostGIS service thật, lint/format/mypy/migration/full 11 tests/downgrade/upgrade. Local tests không dùng thay bằng chứng remote. Run 37213204087 cho source SHA b9bc89518315e0162046846ab141307c01917eb3 (Metro localhost) cũng SUCCESS cả hai job: backend 111468369814, frontend 111468369879; đã kiểm tra log thực tế. [Run mới nhất của source](https://github.com/phamdanghung/delivery-tracking/actions/runs/37213204087).

## 12. Vấn đề nào cần chủ dự án quyết định

**CHƯA CÓ PHÊ DUYỆT** chấp nhận tạm braces/node-forge. Đã gửi phương án: chỉ M0/local dev, repo/config/cert tin cậy, Metro localhost, Compose loopback, giữ 19 high audit findings công khai, review lại trước 2026-11-03 hoặc production (mốc nào đến trước). Review không phải automation đã tự tạo. Không áp dụng cho production hoặc cho phép M1. Chưa nhận quyết định thì không tự chấp nhận rủi ro.

Ngoài M0: native APK/IPA/thiết bị thật, GPS thật, M1–M8/production chưa xác minh. Ba điểm tài liệu cho milestone sau (quyền hẹn giao lại, safety alert states, stale GPS config) giữ nguyên chờ thống nhất; chưa sửa nghiệp vụ.

## 13. Kết luận M0: FAIL

**FAIL — chưa được kết luận M0 hoàn tất.** UUID đã vá và CI remote đã có bằng chứng PASS; toàn bộ build/test/migration/Docker/stack/health đã đạt. **Chỉ còn chờ chủ dự án quyết định rủi ro hai advisory chưa có bản vá.** Không chuyển M1, không làm lại M0, không đổi kiến trúc/nghiệp vụ đã khóa.
