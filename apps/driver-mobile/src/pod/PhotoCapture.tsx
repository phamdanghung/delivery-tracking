import { useEffect, useRef, useState } from "react";
import { Image, Platform, Text } from "react-native";
import * as Picker from "expo-image-picker";
import * as Location from "expo-location";
import { randomUUID } from "expo-crypto";
import { useDriver } from "../driver/context";
import { Button, Field, styles, time } from "../driver/ui";
import { previewAsset, saveAsset } from "./assets";

type Metadata = {
  client_action_id: string; trip_stop_id: string; source: "CAMERA_CAPTURED" | "ALBUM_SELECTED";
  captured_at: string; sha256: string; latitude: number | null; longitude: number | null;
  gps_fix_at: string | null; gps_freshness: "NORMAL" | "STALE" | "INVALID" | "MISSING";
  location_status: "VERIFIED" | "LOCATION_UNVERIFIED"; location_reason: string | null;
};
type Draft = { metadata: Metadata; content_type: string };
type CaptureContext = { id: string; source: Metadata["source"]; stop: string; delivery: string };

export function PhotoCapture({ delivery, stop }: { delivery: string; stop: string }) {
  const state = useDriver(); const [draft, setDraft] = useState<Draft | null>(null);
  const [preview, setPreview] = useState(""); const [reason, setReason] = useState("");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const handling = useRef(false);
  const queued = state.queue.filter((item) => item.command.action.kind === "POD_UPLOAD" && item.command.action.resource_id === delivery && (item.command.action.data as Metadata).trip_stop_id === stop && !["DISCARDED", "CONFLICT", "ERROR"].includes(item.state));
  const alreadyQueued = queued.some((item) => item.command.client_action_id === draft?.metadata.client_action_id);
  const uploaded = (state.cache?.pod_photos?.[delivery] ?? []).filter((item) => item.trip_stop_id === stop);
  const count = new Set([...queued.map((item) => item.command.client_action_id), ...uploaded.map((item) => item.id)]).size;
  async function show(value: Draft) {
    setDraft(value); setReason(value.metadata.location_reason ?? "");
    const uri = await previewAsset(state.user!.id, value.metadata.client_action_id);
    setPreview((old) => { if (Platform.OS === "web" && old.startsWith("blob:")) URL.revokeObjectURL(old); return uri; });
  }
  async function accept(result: Picker.ImagePickerResult, context: CaptureContext) {
    if (result.canceled || !result.assets?.[0]) { await state.savePod("picker", null); return; }
    const asset = result.assets[0];
    const mime = asset.mimeType ?? (/\.png$/i.test(asset.uri) ? "image/png" : "image/jpeg");
    if (!["image/jpeg", "image/png", "image/webp"].includes(mime)) throw new Error("Chọn ảnh JPEG, PNG hoặc WebP");
    const saved = await saveAsset(state.user!.id, context.id, asset.uri);
    let gps: Location.LocationObject | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.granted) gps = await Promise.race([
        Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High }),
        new Promise<null>((resolve) => { timer = setTimeout(() => resolve(null), 10000); }),
      ]);
    } catch { /* DEC-037: reason confirmation permits completion without a valid fix. */ }
    finally { if (timer) clearTimeout(timer); }
    const now = Date.now(); const age = gps ? now - gps.timestamp : Infinity;
    const valid = gps && Number.isFinite(gps.coords.latitude) && Number.isFinite(gps.coords.longitude) && Math.abs(gps.coords.latitude) <= 90 && Math.abs(gps.coords.longitude) <= 180 && age >= 0 && age <= 30000 && !gps.mocked;
    const value: Draft = { content_type: mime, metadata: {
      client_action_id: context.id, trip_stop_id: context.stop, source: context.source,
      captured_at: new Date(now).toISOString(), sha256: saved.sha256,
      latitude: valid ? gps!.coords.latitude : null, longitude: valid ? gps!.coords.longitude : null,
      gps_fix_at: gps && Number.isFinite(gps.timestamp) ? new Date(gps.timestamp).toISOString() : null,
      gps_freshness: valid ? "NORMAL" : !gps ? "MISSING" : age > 30000 ? "STALE" : "INVALID",
      location_status: valid ? "VERIFIED" : "LOCATION_UNVERIFIED", location_reason: null,
    } };
    await state.savePod(context.id, value); await state.savePod(`draft.${context.stop}`, value);
    await state.savePod("picker", null);
    if (context.stop === stop && context.delivery === delivery) await show(value);
    else setError("Đã khôi phục ảnh cho điểm giao trước; mở đúng điểm để xác nhận");
  }
  useEffect(() => {
    let alive = true;
    void (async () => {
      const value = await state.loadPod<Draft>(`draft.${stop}`); if (value && alive) await show(value);
      if (Platform.OS === "android" && !handling.current) {
        handling.current = true;
        try {
          const context = await state.loadPod<CaptureContext>("picker");
          const result = await Picker.getPendingResultAsync();
          if (context && result && "canceled" in result) await accept(result, context);
        } finally { handling.current = false; }
      }
    })().catch((failure) => { if (alive) setError(failure instanceof Error ? failure.message : "Không khôi phục được ảnh"); });
    return () => { alive = false; };
    // Draft is restored once per owner/attempt; queue updates must not reopen a picker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.user?.id, stop]);
  async function pick(camera: boolean) {
    if (busy) return; setBusy(true); setError("");
    try {
      if (Platform.OS !== "web") {
        const permission = camera ? await Picker.requestCameraPermissionsAsync() : await Picker.requestMediaLibraryPermissionsAsync();
        if (!permission.granted) throw new Error("Cần cấp quyền camera/album để lấy ảnh; có thể cấp lại trong Cài đặt");
      }
      const context: CaptureContext = { id: randomUUID(), source: camera ? "CAMERA_CAPTURED" : "ALBUM_SELECTED", stop, delivery };
      // Invoke immediately on web to retain the user's picker gesture.
      const pending = Platform.OS === "web" ? (camera ? Picker.launchCameraAsync({ mediaTypes: ["images"], allowsEditing: false, quality: 1 }) : Picker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsEditing: false, quality: 1 })) : null;
      await state.savePod("picker", context);
      const result = pending ? await pending : camera ? await Picker.launchCameraAsync({ mediaTypes: ["images"], allowsEditing: false, quality: 1 }) : await Picker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsEditing: false, quality: 1 });
      await accept(result, context);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Không lưu được ảnh POD"); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!draft || busy || alreadyQueued) return; setBusy(true); setError("");
    try {
      const value = { ...draft, metadata: { ...draft.metadata, location_reason: draft.metadata.location_status === "LOCATION_UNVERIFIED" ? reason.trim() : null } };
      if (value.metadata.location_status === "LOCATION_UNVERIFIED" && !reason.trim()) throw new Error("Xác nhận lý do vị trí chưa xác minh");
      await state.savePod(value.metadata.client_action_id, value); await state.savePod(`draft.${stop}`, value);
      await state.enqueue({ kind: "POD_UPLOAD", resource_id: delivery, data: value.metadata }); setDraft(value);
      setError("Ảnh đã lưu trên máy và chờ đồng bộ nếu mất mạng");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Không lưu được ảnh"); }
    finally { setBusy(false); }
  }
  return <>
    <Text style={styles.cardTitle}>Ảnh bằng chứng giao hàng</Text>
    <Button title="Chụp ảnh POD" disabled={busy} onPress={() => { void pick(true); }}/>
    <Button title="Chọn từ album" disabled={busy} onPress={() => { void pick(false); }}/>
    {!!preview && <Image source={{ uri: preview }} style={{ width: "100%", height: 220 }} resizeMode="contain" accessibilityLabel="Xem trước ảnh POD"/>}
    {draft && <><Text style={styles.body}>{draft.metadata.source === "CAMERA_CAPTURED" ? "Camera" : "Album"} · {time(draft.metadata.captured_at)} · {draft.metadata.location_status === "VERIFIED" ? "GPS đã xác minh" : "Vị trí chưa xác minh"}</Text>
      {draft.metadata.location_status === "LOCATION_UNVERIFIED" && <Field label="Xác nhận lý do không có vị trí hợp lệ *" value={reason} onChange={setReason}/>}
      <Button title="Xác nhận lưu ảnh POD" disabled={busy || alreadyQueued || (draft.metadata.location_status === "LOCATION_UNVERIFIED" && !reason.trim())} onPress={() => { void save(); }}/></>}
    <Text style={styles.body}>{Math.max(queued.length, uploaded.length)} ảnh đã lưu cho lượt giao này. Không cần chữ ký điện tử.</Text>
    <Button title="Giao thành công" disabled={busy || count === 0} onPress={() => {
      setBusy(true); void state.enqueue({ kind: "STATUS", resource_id: delivery, data: { from_status: "DELIVERING", to_status: "DELIVERED" } }).catch((failure) => setError(failure instanceof Error ? failure.message : "Không lưu được thao tác")).finally(() => setBusy(false));
    }}/>
    {!!error && <Text style={styles.body} accessibilityRole="alert">{error}</Text>}
  </>;
}
