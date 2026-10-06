# M3 — route optimization

Branch `codex/m3-route-optimization`, base M2 merge `206214f06120c5bcf797356a16edf30aceb21594`. Chỉ ROUT-02/ASSET-01, AT-04/12, UX WEB-06/07.

Giữ modular monolith FastAPI, RoutingProvider adapter, OR-Tools, PostGIS và web shell/tokens hiện có. Mục tiêu theo DEC-012: giảm số điểm vi phạm cam kết, sau đó tổng quãng đường, sau đó tổng thời gian. Không dùng penalty thời gian để đổi một điểm đúng hẹn lấy km. Multi-stop, ít nhất ba xe, không hard-code số xe; quá tải warning theo DEC-013. Không M4/offline/geofence, POD upload hoặc customer tracking.

## Quyết định đã chốt

- DEC-030: FIXED_TIME ±15 phút mặc định qua config; service 10 phút qua config, override được. planned_departure_at phải nhập/xác nhận explicit. Không thêm dung sai cho TIME_WINDOW/BEFORE_DEADLINE.
- DEC-031: OSRM self-host local/CI, table + route, ENV URL; không geocoding/Google, không gửi địa chỉ ra ngoài, không chim bay fallback. Dữ liệu đường OSM public có nguồn/hash; dữ liệu fixture chỉ kiểm tra được gắn nhãn, không thay nghiệm thu routing thật.
- DEC-032: lưu/display kết quả vi phạm kèm stop/mức vi phạm, optimize 422 theo baseline; không duyệt/xuất, không override. Overload vẫn warning. Core OR-Tools 9 test giữ nguyên: core tìm tuyến/diagnostic theo DEC-012; approval gate kiểm tra hard windows theo DEC-032.
- planned_departure_at, override service theo từng stop, snapshot input/provider/config và kết quả tối ưu được lưu có migration mới; không sửa baseline. Kết quả cũ không được duyệt khi input/status/config thay đổi.
- Bổ sung không breaking contract M3 có phiên bản cho /trips/{id}/optimize và hành động duyệt cần WEB-07; quyền ADMIN/DISPATCHER, audit/state PLANNED/ASSIGNED đã khóa. Không mở transition mới.
- Tối ưu theo xe/chuyến đã chọn, không tự chuyển đơn sang xe khác; kiểm tra ít nhất ba chuyến/xe với nhiều điểm. Không giới hạn cứng fleet bằng số xe hiện tại.
- DEC-029 chỉ áp dụng M2; exception security M3 không tự suy rộng. Rà soát khi chốt source/runtime, xin quyết định riêng nếu còn advisory.

## Kiểm tra

Ưu tiên test core: đúng hẹn trước km, km trước thời gian, ba kiểu cam kết, multi-stop/ba xe, infeasible/unreachable không mất điểm, không hard capacity gate. Sau source hoàn chỉnh: real provider/PostGIS, migration khi cần, full regression, web build/runtime gates, Docker/health và remote CI/log. Không lặp M0–M2 nếu bằng chứng còn hợp lệ.
