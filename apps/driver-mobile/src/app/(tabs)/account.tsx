import { useState } from "react";
import { Text } from "react-native";
import { useDriver } from "../../driver/context";
import { Button, Card, Login, Page, statusLabel, styles, time } from "../../driver/ui";
import type { PendingAction } from "../../offline/outbox";
export default function Account() {
  const state = useDriver(); const [error, setError] = useState("");
  const [reauth, setReauth] = useState(false);
  if (!state.user) return <Login/>;
  const labels = { WAITING: "Chờ đồng bộ", SYNCING: "Đang đồng bộ", SYNCED: "Đã đồng bộ", ERROR: "Lỗi", CONFLICT: "Cần xử lý", DISCARDED: "Đã bỏ — giữ trong nhật ký" };
  const actions = { START_TRIP: "Bắt đầu chuyến", STATUS: "Cập nhật điểm giao", CORRECT_ARRIVED: "Sửa Đã đến", PROPOSE_RESCHEDULE: "Đề xuất giao lại" };
  const describe = (item: PendingAction) => {
    const action = item.command.action;
    const delivery = state.cache?.deliveries[action.resource_id]?.delivery;
    const data = action.data as { from_status?: string; to_status?: string } | undefined;
    return `${delivery?.code ?? action.resource_id} · ${actions[action.kind]}${data?.from_status && data.to_status ? ` · ${statusLabel[data.from_status]} → ${statusLabel[data.to_status]}` : ""}`;
  };
  return <Page title="Tài khoản"><Card><Text style={styles.cardTitle}>{state.user.full_name}</Text><Text style={styles.body}>Trạng thái đồng bộ</Text>
    <Button title="Đăng nhập lại" disabled={state.busy} onPress={() => setReauth(!reauth)}/>
    {reauth && <Login embedded/>}
    {!!error && <Text style={styles.error}>{error}</Text>}
    {state.queue.map((x) => <Text key={x.command.client_action_id} style={styles.body}>{actions[x.command.action.kind]} — {labels[x.state]} · {time(x.command.occurred_at)}{x.error || x.review?.conflict ? `\n${x.error ?? x.review?.conflict}` : ""}{x.resolution ? `\nQuyết định bỏ: ${x.resolution.reason} · ${time(x.resolution.decided_at)}` : ""}{x.replacement_id ? "\nĐã liên kết thao tác mới" : ""}</Text>)}
    {!state.queue.length && <Text style={styles.body}>Không có thao tác chờ đồng bộ.</Text>}
    {state.queue.filter((x) => x.state === "DISCARDED" && !x.replacement_id).map((x) => <Button key={x.command.client_action_id} title={`Chọn liên kết thao tác mới: ${describe(x)} · ${time(x.command.occurred_at)}`} onPress={() => state.selectReplacement(x.command.client_action_id)}/>)}
    <Button title="Thử lại đồng bộ" disabled={state.busy || !state.online} onPress={() => { void state.retry(); }}/>
    <Button title="Đăng xuất" disabled={state.busy || !state.online} onPress={() => { void state.logout().catch((x: Error) => setError(x.message)); }}/>
  </Card></Page>;
}
