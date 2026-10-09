import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AppState } from "react-native";
import { useNetworkState } from "expo-network";
import { randomUUID } from "expo-crypto";
import { credentials, database } from "../offline/storage";
import { Outbox, entityKeys, finished, type Command, type PendingAction, type Review } from "../offline/outbox";
import { projected } from "./projection";
import { readAsset } from "../pod/assets";

export type Delivery = {
  id: string; code: string; recipient_name: string; recipient_phone: string; address_text: string;
  latitude: number | null; longitude: number | null; notes: string | null; status: string;
  commitment_type: string; appointment_at: string | null; window_start: string | null;
  window_end: string | null; deadline_at: string | null; eta_at: string | null;
  trip_id?: string | null;
};
export type Detail = { delivery: Delivery; events: { id: string; to_status: string; event_time: string; actor_name: string | null; reason: string | null }[] };
export type Trip = { id: string; plate_no: string; status: string; stops: { id: string; delivery_id: string; sequence_no: number; status: string; eta_at: string | null }[] };
export type Cache = {
  trips: Trip[]; deliveries: Record<string, Detail>; saved_at: string;
  route_stops: Record<string, { distance_m: number; violation: string | null; window_end: string | null }>;
  gps: Record<string, { freshness: "NORMAL" | "STALE" | "LOST"; gps_at: string | null }>;
  pod_photos?: Record<string, { id: string; trip_stop_id: string | null }[]>;
};
type Session = { access_token: string; refresh_token: string; user: { id: string; role: string; full_name: string } };
class ApiError extends Error { constructor(readonly status: number, message: string) { super(message); } }
const apiBase = (process.env.EXPO_PUBLIC_API_URL ?? "").replace(/\/$/, "");
type State = {
  user: Session["user"] | null; cache: Cache | null; queue: PendingAction[]; ready: boolean;
  online: boolean; busy: boolean; error: string; login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>; retry: () => Promise<void>; enqueue: (action: Command["action"]) => Promise<void>;
  reviewConflict: (id: string) => Promise<void>; discardConflict: (id: string, reason: string) => Promise<void>;
  replacementId: string | null; selectReplacement: (id: string | null) => void;
  savePod: (id: string, value: unknown) => Promise<void>; loadPod: <T>(id: string) => Promise<T | null>;
};
const Context = createContext<State | null>(null);
export const useDriver = () => { const value = useContext(Context); if (!value) throw new Error("DriverProvider missing"); return value; };

export function DriverProvider({ children }: { children: ReactNode }) {
  const session = useRef<Session | null>(null);
  const store = useRef<Outbox | null>(null);
  const active = useRef<Promise<void> | null>(null);
  const network = useNetworkState();
  const online = network.isConnected !== false;
  const [user, setUser] = useState<Session["user"] | null>(null);
  const [cache, setCache] = useState<Cache | null>(null);
  const [queue, setQueue] = useState<PendingAction[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [replacementId, setReplacementId] = useState<string | null>(null);
  async function raw(path: string, body?: unknown, token?: string) {
    if (!apiBase) throw new Error("Thiếu cấu hình EXPO_PUBLIC_API_URL");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const result = await fetch(`${apiBase}/api/v1/${path}`, {
        method: body === undefined ? "GET" : "POST", signal: controller.signal,
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const data = result.status === 204 ? null : await result.json();
      if (!result.ok) throw new ApiError(result.status, typeof data?.detail === "string" ? data.detail : "Dữ liệu không hợp lệ; vui lòng kiểm tra lại");
      return data;
    } catch (failure) {
      if (failure instanceof ApiError) throw failure;
      throw new Error("Chưa kết nối được máy chủ — dữ liệu và thao tác đã lưu vẫn còn");
    } finally { clearTimeout(timer); }
  }
  async function request(path: string, body?: unknown) {
    const current = session.current;
    if (!current) throw new ApiError(401, "Cần đăng nhập");
    try { return await raw(path, body, current.access_token); }
    catch (failure) {
      if (!(failure instanceof ApiError) || failure.status !== 401) throw failure;
      const renewed: Session = await raw("auth/refresh", { refresh_token: current.refresh_token });
      if (renewed.user.id !== current.user.id || renewed.user.role !== "DRIVER") throw new ApiError(403, "Tài khoản không còn quyền tài xế");
      await credentials.set(JSON.stringify(renewed));
      session.current = renewed;
      return raw(path, body, renewed.access_token);
    }
  }
  async function activate(value: Session) {
    const next = new Outbox(await database, value.user.id);
    await next.init();
    store.current = next; session.current = value;
    setUser(value.user); setCache(await next.load<Cache>("today")); setQueue(await next.list());
    setReplacementId(null);
  }
  async function freshCache(): Promise<Cache> {
    const data: Cache = await request("driver/today");
    const photos = await Promise.all(Object.keys(data.deliveries).map(async (id) => [id, await request(`deliveries/${id}/pod/photos`)] as const));
    return { ...data, pod_photos: Object.fromEntries(photos), saved_at: new Date().toISOString() };
  }
  useEffect(() => {
    let alive = true;
    (async () => {
      try { const saved = await credentials.get(); if (saved && alive) await activate(JSON.parse(saved)); }
      catch { if (alive) setError("Không đọc được dữ liệu đã lưu; vui lòng thử lại"); }
      finally { if (alive) setReady(true); }
    })();
    return () => { alive = false; };
  }, []);
  const refreshQueue = useCallback(() => { void store.current?.list().then(setQueue); }, []);
  async function synchronize() {
    if (!online || !session.current || !store.current) return;
    if (active.current) return active.current;
    setBusy(true);
    active.current = (async () => {
      try {
        const local = store.current!;
        await local.sync(async (command) => {
          try {
            if (command.action.kind === "POD_UPLOAD") {
              const metadata = command.action.data as { sha256: string };
              const asset = await local.load<{ content_type: string }>(`pod.${command.client_action_id}`);
              if (!asset) throw new Error("Không tìm thấy thông tin ảnh đã lưu");
              const bytes = await readAsset(session.current!.user.id, command.client_action_id, metadata.sha256);
              const upload = async () => {
                const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 30000);
                try {
                  const encoded = JSON.stringify(command.action.data).replace(/[^\x20-\x7E]/g, (ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, "0")}`);
                  const result = await fetch(`${apiBase}/api/v1/deliveries/${command.action.resource_id}/pod/photos`, {
                    method: "POST", signal: controller.signal, body: bytes.buffer,
                    headers: { "Content-Type": asset.content_type, "X-POD-Metadata": encoded, Authorization: `Bearer ${session.current!.access_token}` },
                  });
                  if (!result.ok) { const data = await result.json(); throw new ApiError(result.status, typeof data.detail === "string" ? data.detail : "Không upload được ảnh"); }
                } finally { clearTimeout(timer); }
              };
              try { await upload(); }
              catch (failure) {
                if (failure instanceof ApiError && failure.status === 401) { await request("auth/me"); await upload(); }
                else if (!(failure instanceof ApiError && failure.status === 409)) throw failure;
                // 409 goes through the durable command receipt for M4 conflict review/audit.
              }
            }
            const response = await request("driver/actions", command);
            // Persist the acknowledged state before marking SYNCED. A failed refresh
            // must not restore an old ARRIVED after a successful correction.
            const acknowledged = projected(await local.load<Cache>("today"), [{ command, state: "WAITING" }]);
            if (acknowledged) {
              if (command.action.kind === "START_TRIP") acknowledged.trips = acknowledged.trips.map((trip) => trip.id === response.id ? response : trip);
              else if (["STATUS", "CORRECT_ARRIVED"].includes(command.action.kind) && acknowledged.deliveries[response.id]) acknowledged.deliveries[response.id].delivery = response;
              await local.save("today", acknowledged); setCache(acknowledged);
            }
            return { ok: true, retryable: false };
          }
          catch (failure) {
            const status = failure instanceof ApiError ? failure.status : 0;
            if (status === 401 || status === 403) setError("Cần đăng nhập lại hoặc kiểm tra quyền; thao tác đã lưu vẫn còn");
            return { ok: false, conflict: status === 409, retryable: status === 0 || status === 401 || status >= 500,
              error: failure instanceof Error ? failure.message : "Chưa đồng bộ được" };
          }
        }, refreshQueue, async (command, resolution) => {
          try {
            await request("driver/conflicts/resolve", { command, ...resolution });
            const fresh = await freshCache();
            await local.save("today", fresh); setCache(fresh);
            return { ok: true, retryable: false };
          }
          catch (failure) {
            const status = failure instanceof ApiError ? failure.status : 0;
            return { ok: false, retryable: status === 0 || status === 401 || status >= 500, error: failure instanceof Error ? failure.message : "Chưa ghi nhận quyết định bỏ" };
          }
        });
        const fresh = await freshCache();
        await local.save("today", fresh);
        setCache(fresh); setError("");
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : "Chưa kết nối được; dữ liệu đã tải vẫn còn");
      } finally { setBusy(false); refreshQueue(); }
    })().finally(() => { active.current = null; });
    return active.current;
  }
  const syncRef = useRef(synchronize);
  useEffect(() => { syncRef.current = synchronize; });
  useEffect(() => {
    void syncRef.current();
    const timer = setInterval(() => { void syncRef.current(); }, 15000);
    const subscription = AppState.addEventListener("change", (state) => { if (state === "active") void syncRef.current(); });
    return () => { clearInterval(timer); subscription.remove(); };
  }, [online, user?.id]);
  async function login(email: string, password: string) {
    setError(""); setBusy(true);
    try {
      const value: Session = await raw("auth/login", { email, password });
      if (value.user.role !== "DRIVER") throw new Error("Ứng dụng chỉ dành cho tài xế");
      if (session.current && session.current.user.id !== value.user.id && queue.some((x) => !finished(x))) throw new Error("Cần đồng bộ thao tác của tài khoản hiện tại trước khi đổi tài khoản");
      await credentials.set(JSON.stringify(value)); await activate(value);
    } finally { setBusy(false); }
  }
  async function logout() {
    if (active.current) throw new Error("Đợi đồng bộ hoàn tất trước khi đăng xuất");
    if ((await store.current?.list())?.some((x) => !finished(x))) throw new Error("Còn thao tác chưa đồng bộ; vui lòng đồng bộ trước khi đăng xuất");
    await request("auth/logout", { refresh_token: session.current?.refresh_token });
    await credentials.remove(); session.current = null; store.current = null; setUser(null); setCache(null); setQueue([]); setReplacementId(null);
  }
  async function enqueue(action: Command["action"]) {
    if (!store.current) throw new Error("Cần đăng nhập trước khi lưu thao tác");
    const command = { client_action_id: action.kind === "POD_UPLOAD" ? (action.data as { client_action_id: string }).client_action_id : randomUUID(), occurred_at: new Date().toISOString(), action };
    const keys = entityKeys(command, (await store.current.load<Cache>("today"))?.trips);
    const items = await store.current.list();
    if (items.some((x) => x.state === "CONFLICT" && (x.entity_keys ?? entityKeys(x.command)).some((key) => keys.includes(key)))) throw new Error("Điểm giao đang cần xử lý conflict; xem dữ liệu mới và xác nhận bỏ thao tác cũ trước");
    const selected = items.find((x) => x.command.client_action_id === replacementId && x.command.action.resource_id === action.resource_id && (x.command.action.kind === "START_TRIP") === (action.kind === "START_TRIP"));
    await store.current.enqueue(command, keys, selected?.command.client_action_id);
    if (selected) setReplacementId(null);
    refreshQueue(); void syncRef.current();
  }
  async function retry() { setError(""); await store.current?.retry(); await synchronize(); }
  async function reviewConflict(id: string) {
    if (!online || !store.current || active.current) throw new Error("Cần kết nối máy chủ và đợi đồng bộ để xem dữ liệu mới");
    const local = store.current;
    const item = (await local.list()).find((x) => x.command.client_action_id === id && x.state === "CONFLICT");
    if (!item || item.resolution) throw new Error("Conflict đang được xử lý");
    const fresh = await freshCache();
    const review: Review = await request("driver/conflicts/review", item.command);
    await local.save("today", fresh); setCache(fresh);
    await local.reviewed(id, review); setQueue(await local.list());
  }
  async function discardConflict(id: string, reason: string) {
    if (!store.current) throw new Error("Cần đăng nhập");
    await store.current.discard(id, reason, new Date().toISOString());
    setQueue(await store.current.list()); void syncRef.current();
  }
  async function savePod(id: string, value: unknown) { if (!store.current) throw new Error("Cần đăng nhập"); await store.current.save(`pod.${id}`, value); }
  async function loadPod<T>(id: string) { return store.current ? store.current.load<T>(`pod.${id}`) : null; }
  return <Context.Provider value={{ user, cache, queue, ready, online, busy, error, login, logout, retry, enqueue, reviewConflict, discardConflict, replacementId, selectReplacement: setReplacementId, savePod, loadPod }}>{children}</Context.Provider>;
}
