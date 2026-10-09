import { useEffect, useState, type ReactNode } from "react";
import { Link } from "expo-router";
import * as Linking from "expo-linking";
import { ActivityIndicator, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { designTokens as tokens } from "@fleet/shared";
import { useDriver, type Delivery } from "./context";
import { projected } from "./projection";
import { finished, type PendingAction } from "../offline/outbox";

export { projected } from "./projection";

export const statusLabel: Record<string, string> = { CREATED: "Mới tạo", ASSIGNED: "Đã phân", EN_ROUTE: "Đang đi giao", ARRIVED: "Đã đến", DELIVERING: "Đang bàn giao", DELIVERED: "Giao thành công", FAILED: "Giao không thành công", CANCELLED: "Đã hủy", PLANNED: "Đã lên kế hoạch", ACTIVE: "Đang chạy", COMPLETED: "Hoàn tất", RESCHEDULED: "Hẹn giao lại" };
export const time = (value: string | null) => value ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" }) : "Chưa có";
export function commitment(d: Delivery) {
  return d.commitment_type === "FIXED_TIME" ? `Hẹn ${time(d.appointment_at)}` : d.commitment_type === "TIME_WINDOW" ? `${time(d.window_start)} – ${time(d.window_end)}` : `Trước ${time(d.deadline_at)}`;
}
export function Page({ title, children }: { title: string; children: ReactNode }) {
  const state = useDriver();
  const pending = state.queue.filter((x) => !finished(x));
  return <View style={styles.page}>
    <View style={styles.banner}><Text style={styles.body}>{!state.ready ? "Đang đọc dữ liệu đã lưu…" : !state.user ? "Chưa đăng nhập" : !state.online ? "Đang ngoại tuyến — thao tác sẽ được lưu trên máy" : state.busy ? pending.length ? `Đang đồng bộ ${pending.length} thao tác…` : "Đang cập nhật chuyến…" : pending.length ? `${pending.length} thao tác chưa đồng bộ` : state.error ? "Chưa xác minh đồng bộ" : "✓ Đã đồng bộ"}</Text></View>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text accessibilityRole="header" style={styles.title}>{title}</Text>
      {!!state.error && <Text accessibilityRole="alert" style={styles.error}>{state.error}</Text>}
      {!!state.replacementId && <Card><Text style={styles.body}>Đã chọn liên kết với thao tác đã bỏ. Mở đúng điểm giao/chuyến, xem trạng thái hiện tại rồi chọn thao tác mới. Payload cũ không được dùng lại.</Text><Button title="Hủy chọn liên kết" onPress={() => state.selectReplacement(null)}/></Card>}
      {state.queue.filter((x) => x.state === "CONFLICT").map((item) => <ConflictCard key={item.command.client_action_id} item={item}/>)}
      {children}
    </ScrollView>
  </View>;
}
function ConflictCard({ item }: { item: PendingAction }) {
  const state = useDriver();
  const [reason, setReason] = useState(""); const [confirmed, setConfirmed] = useState(false);
  const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const action = item.command.action;
  const labels = { START_TRIP: "Bắt đầu chuyến", STATUS: "Cập nhật trạng thái", PROPOSE_RESCHEDULE: "Đề xuất giao lại", CORRECT_ARRIVED: "Sửa Đã đến nhận sai", POD_UPLOAD: "Tải ảnh POD" };
  const data = action.data as { from_status?: string; to_status?: string; reason?: string } | undefined;
  const known = state.cache?.deliveries[action.resource_id]?.delivery;
  const trip = state.cache?.trips.find((x) => x.id === action.resource_id);
  const detail = item.review?.state.delivery as Delivery | undefined;
  const latest = detail?.status ?? item.review?.state.status;
  async function perform(work: () => Promise<void>) { setSaving(true); setError(""); try { await work(); } catch (x) { setError(x instanceof Error ? x.message : "Chưa xử lý được conflict"); } finally { setSaving(false); } }
  return <Card><Text accessibilityRole="alert" style={styles.error}>CẦN XỬ LÝ — Dữ liệu đã thay đổi</Text>
    <Text style={styles.body}>{known ? `${known.code} · ${known.recipient_name}` : trip ? `Chuyến xe ${trip.plate_no}` : "Thao tác lưu trên máy không còn trong chuyến hiện tại"}</Text>
    <Text style={styles.body}>Thao tác: {labels[action.kind]}{data?.to_status ? ` · ${statusLabel[data.from_status ?? ""] ?? data.from_status} → ${statusLabel[data.to_status] ?? data.to_status}` : ""}</Text>
    {!!data?.reason && <Text style={styles.body}>Lý do cũ: {data.reason}</Text>}
    <Text style={styles.body}>{item.error ?? item.review?.conflict}</Text>
    <Text style={styles.body}>Thao tác cùng điểm giao tạm dừng. Các điểm khác vẫn đồng bộ. Xem dữ liệu mới trước khi quyết định bỏ.</Text>
    <Button title="Xem dữ liệu mới từ máy chủ" disabled={!state.online || state.busy || saving || !!item.resolution} onPress={() => { setConfirmed(false); void perform(() => state.reviewConflict(item.command.client_action_id)); }}/>
    {item.review && <><Text style={styles.body}>{detail?.code ? `${detail.code} · ` : ""}Trạng thái mới: {latest === "NO_LONGER_ASSIGNED" ? "Không còn được phân cho bạn" : !detail && latest === "PLANNED" ? "Đã duyệt" : statusLabel[String(latest)] ?? String(latest)}</Text>
      {detail && <Text style={styles.body}>{commitment(detail)} · ETA {time(detail.eta_at)}</Text>}
      <Button title={confirmed ? "✓ Đã xác nhận xem dữ liệu mới" : "Tôi đã xem dữ liệu mới"} disabled={saving || !!item.resolution} onPress={() => setConfirmed(true)}/>
      <Field label="Lý do bỏ thao tác cũ *" value={reason} onChange={setReason}/>
      <Text style={styles.body}>Bỏ thao tác cũ sẽ được ghi nhật ký. Nếu còn cần thực hiện, chọn thao tác mới theo trạng thái hiện tại.</Text>
      <Button title="Xác nhận bỏ thao tác cũ" danger disabled={!confirmed || !reason.trim() || saving || !!item.resolution} onPress={() => { void perform(() => state.discardConflict(item.command.client_action_id, reason)); }}/></>}
    {!!item.resolution && <Text style={styles.body}>Quyết định bỏ đã lưu trên máy, chờ máy chủ ghi nhận.</Text>}
    {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
  </Card>;
}
export function Card({ children }: { children: ReactNode }) { return <View style={styles.card}>{children}</View>; }
export function Button({ title, onPress, disabled = false, danger = false }: { title: string; onPress: () => void; disabled?: boolean; danger?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={[styles.button, danger && styles.danger, disabled && styles.disabled]}><Text style={styles.buttonText}>{title}</Text></Pressable>;
}
export function Field({ label, value, onChange, secure = false }: { label: string; value: string; onChange: (v: string) => void; secure?: boolean }) {
  return <View style={styles.field}><Text style={styles.body}>{label}</Text><TextInput accessibilityLabel={label} style={styles.input} value={value} onChangeText={onChange} secureTextEntry={secure} autoCapitalize="none" /></View>;
}
export function Login({ embedded = false }: { embedded?: boolean }) {
  const state = useDriver(); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState("");
  const form = <Card><Field label="Email *" value={email} onChange={setEmail}/><Field label="Mật khẩu *" value={password} onChange={setPassword} secure/>
    {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
    <Button title="Đăng nhập" disabled={state.busy || !email || !password || !state.online} onPress={() => { void state.login(email, password).catch((x: Error) => setError(x.message)); }}/>
  </Card>;
  return embedded ? form : <Page title="Đăng nhập tài xế">{form}</Page>;
}
export function Navigation({ delivery }: { delivery: Delivery }) {
  const [error, setError] = useState("");
  return <><Button title="Mở chỉ đường" disabled={delivery.latitude === null || delivery.longitude === null} onPress={() => {
    const coords = `${delivery.latitude},${delivery.longitude}`;
    const url = Platform.OS === "ios" ? `maps://?daddr=${coords}` : Platform.OS === "android" ? `geo:0,0?q=${coords}` : `https://www.google.com/maps/dir/?api=1&destination=${coords}`;
    void Linking.openURL(url).catch(() => setError("Không mở được ứng dụng bản đồ; kiểm tra ứng dụng dẫn đường"));
  }}/>{!!error && <Text style={styles.error}>{error}</Text>}</>;
}
export function Today() {
  const state = useDriver();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10000);
    return () => clearInterval(timer);
  }, []);
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  if (!state.ready) return <Page title="Đang tải"><ActivityIndicator accessibilityLabel="Đang đọc dữ liệu đã lưu"/></Page>;
  if (!state.user) return <Login/>;
  const cache = projected(state.cache, state.queue);
  return <Page title="Hôm nay">
    {!!actionError && <Text accessibilityRole="alert" style={styles.error}>{actionError}</Text>}
    <Button title="Tải lại / Đồng bộ" disabled={state.busy || !state.online} onPress={() => { void state.retry(); }}/>
    {cache && <Text style={styles.caption}>Dữ liệu tải lúc {time(cache.saved_at)}{!state.online ? " — dữ liệu đã lưu" : ""}</Text>}
    {!cache?.trips.length && <Card><Text style={styles.body}>{!state.online ? "Chưa có chuyến đã tải trên máy. Kết nối mạng để tải chuyến được giao." : "Chưa có chuyến được giao hôm nay. Liên hệ điều phối nếu cần."}</Text></Card>}
    {cache?.trips.map((trip) => {
      const next = trip.stops.find((x) => !["DELIVERED", "FAILED", "CANCELLED"].includes(x.status) && !["DELIVERED", "FAILED", "CANCELLED"].includes(cache.deliveries[x.delivery_id]?.delivery.status));
      const d = next && cache.deliveries[next.delivery_id]?.delivery;
      const gps = cache.gps?.[trip.id];
      const age = gps?.gps_at ? (now - new Date(gps.gps_at).getTime()) / 1000 : Infinity;
      const freshness = !gps || age < 0 || age > 120 ? "LOST" : age > 30 && gps.freshness === "NORMAL" ? "STALE" : gps.freshness;
      const leg = d && cache.route_stops?.[d.id];
      return <Card key={trip.id}><Text style={styles.cardTitle}>{trip.plate_no} — {trip.status === "PLANNED" ? "Đã duyệt" : statusLabel[trip.status]}</Text>
        <Text style={styles.body}>{trip.stops.filter((x) => ["DELIVERED", "FAILED", "CANCELLED"].includes(cache.deliveries[x.delivery_id]?.delivery.status) || ["DELIVERED", "FAILED", "CANCELLED"].includes(x.status)).length}/{trip.stops.length} điểm hoàn tất</Text>
        <Text style={styles.body}>{!state.online ? "GPS: vị trí cuối ghi nhận" : freshness === "NORMAL" ? "GPS bình thường" : freshness === "STALE" ? "GPS cập nhật chậm" : "GPS mất tín hiệu"} · {time(gps?.gps_at ?? null)}</Text>
        {trip.status === "PLANNED" && <Button title="Bắt đầu chuyến" disabled={saving} onPress={() => { setSaving(true); void state.enqueue({ kind: "START_TRIP", resource_id: trip.id }).catch((x: Error) => setActionError(x.message)).finally(() => setSaving(false)); }}/>} 
        {d && <View style={styles.next}><Text style={styles.caption}>TIẾP THEO</Text><Text style={styles.cardTitle}>{d.recipient_name}</Text><Text style={styles.body}>{commitment(d)}</Text><Text style={styles.body}>ETA kế hoạch {time(next?.eta_at ?? d.eta_at)}</Text>{leg && <Text style={styles.body}>Chặng dự kiến {(leg.distance_m / 1000).toFixed(1)} km · {leg.violation ? "Có vi phạm giờ hẹn" : "Đúng giờ theo kế hoạch"}</Text>}<Navigation delivery={d}/></View>}
        {trip.stops.map((stop) => { const detail = cache.deliveries[stop.delivery_id]?.delivery; return detail && <Link key={stop.id} href={{ pathname: "/stop/[id]", params: { id: stop.delivery_id } }} style={styles.stop} accessibilityLabel={`Mở điểm ${stop.sequence_no} ${detail.recipient_name}`}><Text>{stop.sequence_no}. {detail.recipient_name} — {statusLabel[detail.status]}</Text></Link>; })}
      </Card>;
    })}
  </Page>;
}
export const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.colors.neutral100 }, content: { padding: 16, gap: 16, paddingBottom: 32 },
  banner: { padding: 12, backgroundColor: tokens.colors.primary50 }, body: { fontSize: 16, lineHeight: 24, color: tokens.colors.neutral950 },
  title: { fontSize: 22, lineHeight: 28, fontWeight: "600", color: tokens.colors.neutral950 }, cardTitle: { fontSize: 17, lineHeight: 24, fontWeight: "600", color: tokens.colors.neutral950 },
  caption: { fontSize: 14, lineHeight: 20, color: tokens.colors.neutral600 }, error: { color: tokens.colors.danger600, fontSize: 16, lineHeight: 24 },
  card: { padding: 16, gap: 12, backgroundColor: "white", borderRadius: 12 }, next: { padding: 16, gap: 12, backgroundColor: tokens.colors.primary50, borderRadius: 12 },
  button: { minHeight: 48, justifyContent: "center", alignItems: "center", backgroundColor: tokens.colors.primary600, borderRadius: 8, padding: 12 }, buttonText: { color: "white", fontSize: 16, fontWeight: "600" }, danger: { backgroundColor: tokens.colors.danger600 }, disabled: { backgroundColor: tokens.colors.neutral600 },
  field: { gap: 8 }, input: { minHeight: 48, borderWidth: 1, borderColor: tokens.colors.neutral300, borderRadius: 8, fontSize: 16, padding: 12, backgroundColor: "white", color: tokens.colors.neutral950 },
  stop: { minHeight: 48, paddingVertical: 12, fontSize: 16, color: tokens.colors.primary600 },
});
