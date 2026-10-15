import { useEffect, useRef, useState } from "react";
import { Image, Platform, Pressable, Text, View } from "react-native";
import { randomUUID } from "expo-crypto";
import * as Picker from "expo-image-picker";
import { useDriver } from "../driver/context";
import { Button, Card, Field, Login, Page, styles, time } from "../driver/ui";
import { previewAsset, saveAsset } from "../pod/assets";

const labels: Record<string, string> = { TOLL: "Phí đường", PARKING: "Bãi xe", HANDLING: "Bốc xếp", OTHER: "Khác" };
type Receipt = { client_action_id: string; trip_id: string; sha256: string; content_type: string; source: "CAMERA_CAPTURED" | "ALBUM_SELECTED"; captured_at: string };
type Draft = { id: string; trip: string; type: string; amount: string; note: string; incurred_at: string; receipt_metadata: Receipt | null };
const empty = (): Draft => ({ id: randomUUID(), trip: "", type: "TOLL", amount: "", note: "", incurred_at: new Date().toISOString(), receipt_metadata: null });

export default function ExpenseScreen() {
  const state = useDriver();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [showTrips, setShowTrips] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<{ id: string; uri: string } | null>(null);
  const restoring = useRef(false);
  const trips = state.cache?.trips.filter((t) => ["ACTIVE", "COMPLETED"].includes(t.status)) ?? [];
  const change = (fields: Partial<Draft>) => setDraft((old) => old ? { ...old, ...fields } : old);
  async function accept(result: Picker.ImagePickerResult, context: { id: string; trip: string; source: Receipt["source"] }) {
    if (result.canceled || !result.assets?.[0]) { await state.savePod("expense.picker", null); return; }
    const asset = result.assets[0];
    const mime = asset.mimeType ?? (/\.png$/i.test(asset.uri) ? "image/png" : "image/jpeg");
    if (!["image/png", "image/jpeg", "image/webp"].includes(mime)) throw new Error("Chọn ảnh JPEG, PNG hoặc WebP");
    const stored = await saveAsset(state.user!.id, context.id, asset.uri);
    const receipt: Receipt = { client_action_id: context.id, trip_id: context.trip, sha256: stored.sha256, content_type: mime, source: context.source, captured_at: new Date().toISOString() };
    setDraft((old) => ({ ...(old ?? empty()), id: context.id, trip: context.trip, receipt_metadata: receipt }));
    await state.savePod("expense.picker", null);
  }
  useEffect(() => {
    if (!state.user || restoring.current) return;
    restoring.current = true;
    void (async () => {
      const saved = await state.loadPod<Draft>("expense.draft");
      const consumed = saved && state.queue.some((x) => x.command.client_action_id === saved.id);
      setDraft(saved && !consumed ? saved : empty());
      if (Platform.OS === "android") {
        const context = await state.loadPod<{ id: string; trip: string; source: Receipt["source"] }>("expense.picker");
        if (context) { const result = await Picker.getPendingResultAsync(); if (result && "canceled" in result) await accept(result, context); }
      }
    })().catch((failure) => setError(failure instanceof Error ? failure.message : "Không khôi phục được chi phí"));
    // Restore once per owner; queue refresh must not reopen the native picker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.user?.id]);
  useEffect(() => {
    if (draft && state.user) void state.savePod("expense.draft", draft).catch(() => setError("Chưa lưu được nháp trên máy; vui lòng thử lại"));
    // Persist edits through the existing owner-scoped SQLite store.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, state.user?.id]);
  useEffect(() => {
    let alive = true; let uri = "";
    if (draft?.receipt_metadata && state.user) void previewAsset(state.user.id, draft.id).then((value) => {
      uri = value; if (alive) setPreview({ id: draft.id, uri: value }); else if (Platform.OS === "web" && value.startsWith("blob:")) URL.revokeObjectURL(value);
    }).catch(() => setError("Không đọc được ảnh đã lưu"));
    return () => { alive = false; if (Platform.OS === "web" && uri.startsWith("blob:")) URL.revokeObjectURL(uri); };
  }, [draft?.id, draft?.receipt_metadata, state.user]);
  async function pick(camera: boolean) {
    if (!draft?.trip || busy) return;
    setBusy(true); setError("");
    try {
      if (Platform.OS !== "web") {
        const permission = camera ? await Picker.requestCameraPermissionsAsync() : await Picker.requestMediaLibraryPermissionsAsync();
        if (!permission.granted) throw new Error("Cần cấp quyền camera/album để lấy biên lai; ảnh không bắt buộc");
      }
      const context = { id: randomUUID(), trip: draft.trip, source: (camera ? "CAMERA_CAPTURED" : "ALBUM_SELECTED") as Receipt["source"] };
      const options: Picker.ImagePickerOptions = { mediaTypes: ["images"], allowsEditing: false, quality: 1 };
      const pending = Platform.OS === "web" ? (camera ? Picker.launchCameraAsync(options) : Picker.launchImageLibraryAsync(options)) : null;
      await state.savePod("expense.picker", context);
      await accept(pending ? await pending : camera ? await Picker.launchCameraAsync(options) : await Picker.launchImageLibraryAsync(options), context);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Không lưu được biên lai"); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!draft || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (!trips.some((t) => t.id === draft.trip)) throw new Error("Chọn chuyến đang chạy hoặc đã hoàn tất của bạn");
      if (!/^\d{1,12}(\.\d{1,2})?$/.test(draft.amount.trim())) throw new Error("Nhập số tiền hợp lệ, tối đa hai chữ số thập phân");
      await state.enqueue({ kind: "EXPENSE_CREATE", resource_id: draft.trip, data: { type: draft.type, amount: draft.amount.trim(), note: draft.note.trim() || null, incurred_at: draft.incurred_at, receipt_metadata: draft.receipt_metadata } }, draft.id);
      setNotice("Đã lưu chi phí trên máy; xem trạng thái đồng bộ bên dưới."); setDraft(empty());
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Chưa lưu được; nội dung vẫn được giữ"); }
    finally { setBusy(false); }
  }
  if (!state.user) return <Login />;
  const pending = state.queue.filter((x) => x.command.action.kind === "EXPENSE_CREATE" && x.state !== "SYNCED");
  const queueLabels = { WAITING: "Chờ đồng bộ", SYNCING: "Đang đồng bộ", ERROR: "Lỗi — cần thử lại", CONFLICT: "Cần xử lý — xem trạng thái mới", DISCARDED: "Đã bỏ thao tác, giữ lịch sử", SYNCED: "Đã đồng bộ" };
  return <Page title="Chi phí"><Card>
    <Text style={styles.cardTitle}>Chi phí của tôi</Text><Text style={styles.caption}>Biên lai không bắt buộc. Chi phí và ảnh được giữ trên máy khi ngoại tuyến.</Text>
    {!trips.length && <Text style={styles.body}>Chưa có chuyến đang chạy/hoàn tất trong dữ liệu đã tải.</Text>}
    <Button title={draft?.trip ? `Chuyến xe ${trips.find((trip) => trip.id === draft.trip)?.plate_no ?? "cần chọn lại"} · ${draft.trip.slice(0,8)} — đổi chuyến` : "Chọn chuyến *"} disabled={busy || !trips.length} onPress={() => setShowTrips(!showTrips)} />
    {showTrips && trips.map((trip) => <Button key={trip.id} title={`${draft?.trip === trip.id ? "✓ " : ""}${trip.plate_no} · ${trip.status === "ACTIVE" ? "Đang chạy" : "Hoàn tất"} · ${trip.id.slice(0, 8)}`} disabled={busy} onPress={() => { if (draft?.trip !== trip.id) change({ trip: trip.id, receipt_metadata: null, id: randomUUID() }); setShowTrips(false); }} />)}
    <Text style={styles.body}>Loại chi phí *</Text><View style={{ gap: 8, flexDirection:"row",flexWrap:"wrap" }}>{Object.entries(labels).map(([key, label]) => <Pressable key={key} accessibilityRole="radio" accessibilityLabel={label} accessibilityState={{selected:draft?.type===key,disabled:busy}} disabled={busy} onPress={() => change({type:key})} style={[styles.button,{width:"48%",backgroundColor:draft?.type===key ? styles.button.backgroundColor : "white",borderWidth:1,borderColor:styles.button.backgroundColor}]}><Text style={draft?.type===key ? styles.buttonText : styles.body}>{label}</Text></Pressable>)}</View>
    <Field label="Số tiền (VND) *" value={draft?.amount ?? ""} onChange={(amount) => change({ amount })} />
    <Field label="Ghi chú" value={draft?.note ?? ""} onChange={(note) => change({ note })} />
    <Button title="Chụp biên lai (tùy chọn)" disabled={busy || !draft?.trip} onPress={() => { void pick(true); }} />
    <Button title="Chọn biên lai từ album" disabled={busy || !draft?.trip} onPress={() => { void pick(false); }} />
    {preview && preview.id === draft?.id && draft?.receipt_metadata && <Image accessibilityLabel="Ảnh biên lai đã lưu trên máy" source={{ uri: preview.uri }} style={{ width: "100%", height: 200, resizeMode: "contain" }} />}
    {draft?.receipt_metadata && <Button title="Bỏ ảnh khỏi bản nháp" disabled={busy} onPress={() => change({ receipt_metadata: null, id: randomUUID() })} />}
    {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}{!!notice && <Text accessibilityRole="alert" style={styles.body}>{notice}</Text>}
    <Button title={busy ? "Đang lưu…" : "Lưu chi phí"} disabled={busy || !draft?.trip || !draft?.amount} onPress={() => { void save(); }} />
    </Card><Card><Text style={styles.cardTitle}>Trạng thái đồng bộ</Text>
    {pending.map((item) => <Text key={item.command.client_action_id} style={styles.body}>{labels[(item.command.action.data as { type: string }).type]} · {queueLabels[item.state]}{item.error ? ` · ${item.error}` : ""}</Text>)}
    {!pending.length && <Text style={styles.body}>Không có chi phí đang chờ.</Text>}<Button title="Đồng bộ / thử lại" disabled={!state.online || state.busy} onPress={() => { void state.retry(); }} />
    </Card><Card><Text style={styles.cardTitle}>Chi phí đã ghi nhận</Text>
    {(state.cache?.expenses ?? []).map((item) => <View key={item.id}><Text style={styles.body}>{labels[item.type] ?? item.type} · {Number(item.amount).toLocaleString("vi-VN")} VND</Text><Text style={styles.caption}>{time(item.incurred_at)}{item.receipt_id ? " · Có ảnh biên lai" : ""}</Text>{item.note && <Text style={styles.body}>{item.note}</Text>}</View>)}
    {!state.cache?.expenses?.length && <Text style={styles.body}>Chưa có chi phí đã ghi nhận trong dữ liệu đã tải.</Text>}
  </Card></Page>;
}
