# M0 — Dependency Security Review

Ngày kiểm tra: 2026-10-04. Phạm vi: M0; không thay nghiệp vụ hoặc kiến trúc.

## Toàn bộ 26 findings ban đầu

A = package có code runtime của sản phẩm, nhưng advisory cụ thể lan truyền từ tooling. B = build/dev/tooling. C = transitive; C là quan hệ dependency, không phải một loại attack surface riêng. npm `dependencies`/`devDependencies` không đủ để suy ra runtime.

| Package | Mức | Vai trò | Trực tiếp / transitive | Advisory gốc |
|---|---|---|---|---|
| @expo/cli | high | B; A: runtime module-loader helper | C: transitive | node-forge, uuid, braces |
| @expo/code-signing-certificates | high | B | C: transitive | node-forge |
| @expo/config | moderate | B | C: transitive | uuid |
| @expo/config-plugins | moderate | B | C: transitive | uuid |
| @expo/inline-modules | moderate | B | C: transitive | uuid |
| @expo/local-build-cache-provider | moderate | B | C: transitive | uuid |
| @expo/metro | high | B | C: transitive | braces |
| @expo/metro-config | high | B | C: transitive | uuid, braces |
| @expo/metro-file-map | high | B | C: transitive | braces |
| @expo/prebuild-config | moderate | B | C: transitive | uuid |
| @next/eslint-plugin-next | high | B | C: transitive | braces |
| @react-native/community-cli-plugin | high | B | C: transitive | braces |
| @react-native/virtualized-lists | high | A; advisory tooling | C: transitive | braces |
| braces | high | B | C: transitive | braces |
| eslint-config-next | high | B | Trực tiếp | braces |
| expo | high | A; advisory tooling | Trực tiếp | node-forge, uuid, braces |
| fast-glob | high | B | C: transitive | braces |
| metro | high | B | C: transitive | braces |
| metro-config | high | B | C: transitive | braces |
| metro-file-map | high | B | C: transitive | braces |
| metro-transform-worker | high | B | C: transitive | braces |
| micromatch | high | B | C: transitive | braces |
| node-forge | high | B | C: transitive | node-forge |
| react-native | high | A; advisory tooling | Trực tiếp | braces |
| uuid | moderate | B | C: transitive | uuid |
| xcode | moderate | B | C: transitive | uuid |

26 affected-package entries là kết quả lan truyền của 3 advisory gốc, không phải 26 CVE độc lập. Trong bảng, 3 package A không đồng nghĩa có đường khai thác advisory từ code runtime.

## Toàn bộ đường dependency từ workspace

Danh sách từ lockfile trước sửa, resolve theo vị trí node_modules, dereference workspace links. Bao gồm dependencies/optionalDependencies và devDependencies của workspace. Chỉ liệt kê simple paths (không lặp package trong chu kỳ); peer quan hệ không coi là cạnh gọi code. Lockfile vị trí và dữ liệu gốc đầy đủ lưu tại artifacts/m0-revision-analysis-before.json.

### braces: 20 đường

- `@fleet/admin-web@0.0.0 → eslint-config-next@16.3.8 → @next/eslint-plugin-next@16.3.8 → fast-glob@3.3.1 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro@56.0.2 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro@56.0.2 → metro-config@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro@56.0.2 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro@56.0.2 → metro-transform-worker@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro-config@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro-transform-worker@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro-file-map@57.0.3 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro@56.0.2 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro@56.0.2 → metro-config@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro@56.0.2 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro@56.0.2 → metro-transform-worker@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro-config@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro-config@57.0.12 → @expo/metro@56.0.2 → metro-transform-worker@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → react-native@0.86.3 → @react-native/community-cli-plugin@0.86.3 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`
- `@fleet/driver-mobile@0.0.0 → react-native@0.86.3 → @react-native/community-cli-plugin@0.86.3 → metro-config@0.84.5 → metro@0.84.5 → metro-file-map@0.84.5 → micromatch@4.0.8 → braces@3.0.3`

### node-forge: 2 đường

- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/code-signing-certificates@0.0.6 → node-forge@1.4.0`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → node-forge@1.4.0`

### uuid: 10 đường

- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/config@57.0.9 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/inline-modules@0.1.7 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/metro-config@57.0.12 → @expo/config@57.0.9 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/prebuild-config@57.0.16 → @expo/config@57.0.9 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/cli@57.0.27 → @expo/prebuild-config@57.0.16 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/config@57.0.9 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/local-build-cache-provider@57.0.8 → @expo/config@57.0.9 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`
- `@fleet/driver-mobile@0.0.0 → expo@57.0.26 → @expo/metro-config@57.0.12 → @expo/config@57.0.9 → @expo/config-plugins@57.0.9 → xcode@3.0.1 → uuid@7.0.3`

## Advisory, xử lý và giới hạn

- [uuid GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq): override có phạm vi xcode sang 11.1.1, bản vá CommonJS; không dùng bản mới ESM-only. xcode dùng v4() để tạo ID Xcode, không dùng các hàm/buffer dễ bị tấn công. Test thực tế xác minh xcode tạo 1.000 ID đúng định dạng/không trùng, cùng regression v5 buffer ngắn. Audit giảm 7 moderate entries; vẫn giữ toàn bộ audit high.
- [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): <=3.0.3, chưa có bản vá. micromatch 4.0.8 và fast-glob 3.3.1 hiện vẫn phụ thuộc braces; nâng cha trong stack tương thích không loại advisory. Cơ chế là đệ quy glob lồng sâu gây stack exhaustion, ảnh hưởng availability build/lint/Metro watcher. Dữ liệu đơn hàng hoặc request API M0 không được đưa vào glob parser. Rủi ro còn nếu developer/build chấp nhận pattern/config không tin cậy; không đánh giá là zero.
- [node-forge GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv): <=1.4.0, chưa có bản vá. Expo CLI 57.0.27 và certificates 0.0.6 dùng forge; certificates 0.0.7 cũng vẫn cần forge ^1.4.0. Các call site: CLI iOS Security.js; certificates main.js kiểm tra chứng chỉ/chữ ký/CSR; codesigning.js xử lý ký development manifest. Rủi ro chữ ký/chứng chỉ không tin cậy trong tooling, có thể ảnh hưởng integrity; không nói rằng chưa dùng tính năng đồng nghĩa package an toàn.

## Bằng chứng runtime và rủi ro thực tế

- Mobile: Expo runtime entry src/Expo.ts không import CLI; CLI là bin riêng. Các bundle Android/iOS thực sự được export kèm source map; scripts/verify_mobile_surface.mjs xác minh không chứa braces, node-forge, uuid, xcode, micromatch hoặc Expo certificates. Expo có nhúng duy nhất @expo/cli/build/metro-require/require.js làm module-loader runtime: file này không import các primitive glob/crypto dễ bị tấn công. Gate kiểm tra riêng file này và vẫn fail nếu có CLI source khác. Run CI đầu tiên phát hiện helper này; đã sửa phân loại dựa trên source, không lọc audit. Kết quả cụ thể ghi trong M0_FINAL_REVISION.md. Không cài expo-updates hoặc cấu hình OTA code-signing trong app M0.
- Web: 5 Next.js server trace (*.nft.json) trước sửa không chứa package gốc advisory. Docker web hiện cài workspace tooling trong node_modules, nên không được tuyên bố package đã bị loại khỏi image. Route M0 là skeleton tĩnh, không nhận glob/certificate từ khách; trace sau rebuild phải kiểm tra lại. Chứng cứ này có phạm vi các route và bundle M0 hiện tại, không đảm bảo mọi code tương lai.
- Backend: Python, không import npm graph. Stack PostgreSQL/Redis/MinIO/Traccar không chạy các package npm này.
- Đánh giá: không thấy đường input khách hàng tới 2 primitive dễ bị tấn công trong runtime M0 đã export/build. Rủi ro trực tiếp runtime M0 thấp theo bằng chứng hiện có; rủi ro tooling vẫn còn và mức advisory high được giữ nguyên. Không chấp nhận tài liệu/package/cert/config không tin cậy; không expose Metro ra mạng; Compose bind loopback. Chưa chứng nhận production.

## Các phương án đã xem xét

- Giữ Expo SDK 57.0.26, RN 0.86.3; Expo CLI/config-plugins/xcode tương thích hiện tại chưa có bản nâng loại forge/braces.
- Override UUID có bản vá, API CommonJS/v4 tương thích và có kiểm tra thực tế. npm 11 báo invalid dù cài đúng: [npm/cli#9514](https://github.com/npm/cli/issues/9514). npm 12.2.0 đã nhận override; cố định npm cho local/Docker/CI. Node tương thích ^22.22.2 hoặc ^24.15.0 hoặc >=26.
- Thay forge bằng thư viện crypto khác hoặc braces bằng parser khác không tương thích API của cha; không có drop-in patch đã được chứng minh. Không viết crypto/parser tự chế hoặc buộc dependency khác chỉ để audit về 0. Chờ upstream fix rồi nâng, chạy lại toàn bộ gates.
- Không dùng npm audit fix --force; không ignore/suppress advisory; không hạ SDK.

## Quyết định chờ chủ dự án

Đề xuất chấp nhận tạm 2 advisory chưa có bản vá chỉ cho M0/local development: tooling chỉ dùng repo/config/cert tin cậy, Metro chỉ loopback, audit vẫn công khai 19 high entries, kiểm tra lại chậm nhất 2026-11-03 hoặc trước triển khai production (mốc nào đến trước). Việc review là yêu cầu quy trình, không có automation được tự tạo. Không tự phê duyệt; chưa có quyết định thì M0 FAIL. Chấp nhận này không cho phép M1 hoặc production.
