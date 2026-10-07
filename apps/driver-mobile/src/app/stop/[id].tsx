import { useState } from "react";
import { useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import { Text } from "react-native";
import { useDriver } from "../../driver/context";
import { Button, Card, Field, Login, Navigation, Page, commitment, projected, statusLabel, styles, time } from "../../driver/ui";
export default function StopDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(); const state = useDriver();
  const [reason, setReason] = useState(""); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const [kind, setKind] = useState("FIXED_TIME"); const [date, setDate] = useState("");
  const [at, setAt] = useState(""); const [end, setEnd] = useState("");
  if (!state.user) return <Login/>;
  const cache = projected(state.cache, state.queue); const detail = cache?.deliveries[id];
  if (!detail) return <Page title="Điểm giao"><Text style={styles.body}>Chưa tải điểm giao hoặc không còn quyền truy cập.</Text></Page>;
  const d = detail.delivery;
  const trip = cache?.trips.find((x) => x.stops.some((stop) => stop.delivery_id === id));
  const arrival = [...detail.events].reverse().find((x) => x.to_status === "ARRIVED");
  const submit = async (kind: "STATUS" | "CORRECT_ARRIVED" | "PROPOSE_RESCHEDULE", data: unknown) => {
    if (saving) return; setSaving(true); setError("");
    try { await state.enqueue({ kind, resource_id: id, data }); setError("Đã lưu trên máy — chờ đồng bộ"); }
    catch (x) { setError(x instanceof Error ? x.message : "Không lưu được thao tác; vui lòng thử lại"); }
    finally { setSaving(false); }
  };
  return <Page title={d.recipient_name}><Card>
    <Text style={styles.body}>{statusLabel[d.status]}</Text><Text style={styles.body}>{commitment(d)}</Text><Text style={styles.body}>ETA {time(d.eta_at)}</Text>
    <Text style={styles.body}>{d.address_text}</Text><Text style={styles.body}>{d.recipient_phone}</Text><Button title="Gọi khách" onPress={() => { void Linking.openURL(`tel:${encodeURIComponent(d.recipient_phone)}`).catch(() => setError("Không mở được cuộc gọi")); }}/>
    <Navigation delivery={d}/>{!!d.notes && <Text style={styles.body}>Ghi chú: {d.notes}</Text>}
    {!!error && <Text accessibilityRole="alert" style={styles.body}>{error}</Text>}
    {trip?.status === "ACTIVE" && d.status === "ARRIVED" && <>
      <Button title="Bắt đầu bàn giao" disabled={saving} onPress={() => { void submit("STATUS", { from_status: "ARRIVED", to_status: "DELIVERING" }); }}/>
      <Text style={styles.body}>Sửa Đã đến nhận sai sẽ được ghi nhật ký và đưa điểm về Đang đi giao.</Text><Field label="Lý do sửa / giao thất bại *" value={reason} onChange={setReason}/>
      <Button title="Xác nhận sửa Đã đến" disabled={saving || !reason.trim() || !arrival} onPress={() => { void submit("CORRECT_ARRIVED", { arrival_event_id: arrival?.id, reason }); }}/>
    </>}
    {trip?.status === "ACTIVE" && d.status === "DELIVERING" && <><Text style={styles.body}>Cần ảnh bằng chứng hợp lệ để hoàn tất giao hàng.</Text><Button title="Giao thành công" onPress={() => {}} disabled/><Field label="Lý do giao thất bại *" value={reason} onChange={setReason}/></>}
    {trip?.status === "ACTIVE" && ["ARRIVED", "DELIVERING"].includes(d.status) && <Button title="Xác nhận giao không thành công" danger disabled={saving || !reason.trim()} onPress={() => { void submit("STATUS", { from_status: d.status, to_status: "FAILED", reason }); }}/>} 
    {d.status === "FAILED" && <>
      <Text style={styles.cardTitle}>Đề xuất giao lại</Text><Text style={styles.body}>Lịch mới chỉ có hiệu lực sau khi điều phối xác nhận.</Text>
      <Field label="Ngày giao YYYY-MM-DD *" value={date} onChange={setDate}/>
      <Button title={`Kiểu hẹn: ${kind === "FIXED_TIME" ? "Giờ cố định" : kind === "TIME_WINDOW" ? "Khung giờ" : "Trước mốc"} — đổi kiểu`} disabled={saving} onPress={() => setKind(kind === "FIXED_TIME" ? "TIME_WINDOW" : kind === "TIME_WINDOW" ? "BEFORE_DEADLINE" : "FIXED_TIME")}/>
      <Field label="Thời gian YYYY-MM-DDTHH:mm (giờ công ty UTC+7) *" value={at} onChange={setAt}/>
      {kind === "TIME_WINDOW" && <Field label="Kết thúc khung giờ YYYY-MM-DDTHH:mm *" value={end} onChange={setEnd}/>}
      <Button title="Xác nhận đề xuất giao lại" disabled={saving || !date || !at || (kind === "TIME_WINDOW" && !end)} onPress={() => {
        try {
          if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(at) || (kind === "TIME_WINDOW" && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(end))) throw new Error("Kiểm tra ngày và giờ theo định dạng hiển thị");
          const day = new Date(`${date}T00:00:00Z`);
          if (!Number.isFinite(day.getTime()) || day.toISOString().slice(0, 10) !== date) throw new Error("Ngày giao không hợp lệ");
          const when = new Date(`${at}:00+07:00`); const finish = new Date(`${end}:00+07:00`);
          if (!Number.isFinite(when.getTime()) || when.getTime() <= Date.now()) throw new Error("Lịch giao lại phải ở tương lai");
          if (kind === "TIME_WINDOW" && (!Number.isFinite(finish.getTime()) || finish < when)) throw new Error("Khung giờ kết thúc phải sau bắt đầu");
          const commitment = { commitment_type: kind, scheduled_date: date, ...(kind === "FIXED_TIME" ? { appointment_at: when.toISOString() } : kind === "TIME_WINDOW" ? { window_start: when.toISOString(), window_end: finish.toISOString() } : { deadline_at: when.toISOString() }) };
          void submit("PROPOSE_RESCHEDULE", { commitment });
        } catch (x) { setError(x instanceof Error ? x.message : "Kiểm tra lịch giao lại"); }
      }}/>
    </>}
  </Card><Card><Text style={styles.cardTitle}>Lịch sử trạng thái</Text>{detail.events.map((x) => <Text key={x.id} style={styles.body}>{statusLabel[x.to_status] ?? x.to_status} · {time(x.event_time)} · {x.actor_name ?? "Hệ thống"}{x.reason ? `\n${x.reason}` : ""}</Text>)}</Card></Page>;
}
