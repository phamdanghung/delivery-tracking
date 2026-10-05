"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import DispatchWorkspace, { type DispatchView } from "../dispatch/workspace";
import {
  engineLabels,
  gpsFreshness,
  gpsLabels,
  type Position,
} from "./gps-state";
const Map = dynamic(() => import("./map"), {
  ssr: false,
  loading: () => <p role="status">Đang tải bản đồ…</p>,
});
type User = {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  role: "ADMIN" | "DISPATCHER" | "DRIVER";
  is_active: boolean;
};
type Vehicle = {
  id: string;
  plate_no: string;
  name: string | null;
  vehicle_type: string | null;
  max_weight_kg: number | null;
  max_volume_m3: number | null;
  traccar_device_id: number | null;
  status: string;
};
type Live = {
  position: Position | null;
  freshness: string;
  reason: string | null;
};
type Driver = {
  id: string;
  full_name: string;
  active: boolean;
  is_active: boolean;
  vehicle_assignments: {
    vehicle_id: string;
    trip_id: string;
    status: string;
  }[];
};
type History = {
  segments: Position[][];
  points: Position[];
  gaps: { from: string; to: string }[];
  stops: {
    started_at: string;
    ended_at: string;
    duration_seconds: number;
    engine_state: keyof typeof engineLabels;
  }[];
};
class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const response = await fetch(`/api/internal/${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof body.detail === "string"
        ? body.detail
        : "Dữ liệu chưa hợp lệ. Kiểm tra các trường và thử lại.",
    );
  return body;
}
const time = (value: string | null) =>
  value ? new Date(value).toLocaleString("vi-VN") : "Chưa có dữ liệu";
const message = (value: unknown) =>
  value instanceof Error ? value.message : "Không thể kết nối hệ thống";
export default function FleetConsole({
  view = "live",
  vehicleId,
  dispatchView,
  entityId,
}: {
  view?: "live" | "vehicles" | "users" | "history" | "deliveries" | "trips";
  vehicleId?: string;
  dispatchView?: DispatchView;
  entityId?: string;
}) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [show, setShow] = useState(false),
    [busy, setBusy] = useState(false);
  const expire = useCallback(() => {
    setUser(null);
    setError("Phiên đăng nhập đã hết hiệu lực. Vui lòng đăng nhập lại.");
  }, []);
  useEffect(() => {
    api<User>("auth/me")
      .then(setUser)
      .catch((value) => {
        if (!(value instanceof ApiError && value.status === 401))
          setError(message(value));
      })
      .finally(() => setLoading(false));
  }, []);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      setUser(
        (
          await api<{ user: User }>("auth/login", "POST", {
            email: form.get("email"),
            password: form.get("password"),
          })
        ).user,
      );
    } catch (value) {
      setError(message(value));
    } finally {
      setBusy(false);
    }
  }
  if (loading)
    return (
      <main aria-busy="true">
        <h1>Quản lý xe giao hàng</h1>
        <p role="status">Đang kiểm tra phiên đăng nhập…</p>
      </main>
    );
  if (!user)
    return (
      <main className="login">
        <span className="eyebrow">QUẢN LÝ XE GIAO HÀNG</span>
        <h1>Đăng nhập nội bộ</h1>
        <form onSubmit={login}>
          <label>
            Email *
            <input name="email" type="email" autoComplete="username" required />
          </label>
          <label>
            Mật khẩu *
            <input
              name="password"
              type={show ? "text" : "password"}
              autoComplete="current-password"
              required
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={show}
              onChange={(e) => setShow(e.target.checked)}
            />
            Hiện mật khẩu
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button disabled={busy}>
            {busy ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
        </form>
      </main>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <strong>
          Quản lý xe
          <br />
          giao hàng
        </strong>
        <nav aria-label="Điều hướng">
          {user.role !== "DRIVER" && (
            <>
              <Link
                href="/deliveries"
                aria-current={view === "deliveries" ? "page" : undefined}
              >
                Đơn giao
              </Link>
              <Link
                href="/trips"
                aria-current={view === "trips" ? "page" : undefined}
              >
                Chuyến giao
              </Link>
            </>
          )}
          <a
            href="/fleet/live"
            aria-current={view === "live" ? "page" : undefined}
          >
            Bản đồ trực tiếp
          </a>
          <a
            href="/fleet/vehicles"
            aria-current={view === "vehicles" ? "page" : undefined}
          >
            Danh sách xe
          </a>
          <a href="/fleet/live#history">Lịch sử hành trình</a>
          {user.role === "ADMIN" && (
            <a
              href="/admin/users"
              aria-current={view === "users" ? "page" : undefined}
            >
              Người dùng & phân quyền
            </a>
          )}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>{new Date().toLocaleDateString("vi-VN")}</span>
          <span>
            {user.full_name} · {user.role}
          </span>
          <button
            className="secondary"
            onClick={async () => {
              try {
                await api("auth/logout", "POST", {});
              } catch {
                setError(
                  "Đã đăng xuất trên trình duyệt; chưa kết nối được hệ thống để thu hồi phiên server.",
                );
              } finally {
                setUser(null);
              }
            }}
          >
            Đăng xuất
          </button>
        </header>
        {user.role === "DRIVER" ? (
          <main>
            <h1>Không có quyền truy cập</h1>
            <p role="alert">
              Tài xế không được xem toàn bộ đội xe hoặc lịch sử xe.
            </p>
          </main>
        ) : view === "deliveries" || view === "trips" ? (
          <DispatchWorkspace
            api={api}
            view={dispatchView || (view === "trips" ? "trips" : "list")}
            entityId={entityId}
            onExpired={expire}
          />
        ) : (
          <FleetData
            user={user}
            view={view}
            vehicleId={vehicleId}
            onExpired={expire}
          />
        )}
      </div>
    </div>
  );
}
function FleetData({
  user,
  view,
  vehicleId,
  onExpired,
}: {
  user: User;
  view: string;
  vehicleId?: string;
  onExpired: () => void;
}) {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [drivers, setDrivers] = useState<Driver[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [live, setLive] = useState<Record<string, Live>>({}),
    [outages, setOutages] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState(vehicleId || ""),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [permission, setPermission] = useState(false),
    [now, setNow] = useState(() => Date.now()),
    [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Vehicle | null>(null),
    [formOpen, setFormOpen] = useState(false),
    [devices, setDevices] = useState<
      { id: number; name: string; uniqueId: string }[]
    >([]);
  const [history, setHistory] = useState<History | null>(null),
    [historyBusy, setHistoryBusy] = useState(false),
    [historyError, setHistoryError] = useState(""),
    [playback, setPlayback] = useState(0),
    [distance, setDistance] = useState<number | null>(null);
  const historyForm = useRef<HTMLFormElement>(null);
  const [actionError, setActionError] = useState("");
  const polling = useRef(false);
  const refresh = useCallback(async () => {
    if (polling.current) return;
    polling.current = true;
    try {
      if (view === "users") setUsers(await api<User[]>("users"));
      else {
        const list = await api<Vehicle[]>("vehicles");
        setVehicles(list);
        setDrivers(await api<Driver[]>("drivers"));
        await Promise.all(
          list.map(async (vehicle) => {
            try {
              const data = await api<Live>(`vehicles/${vehicle.id}/live`);
              setLive((p) => ({ ...p, [vehicle.id]: data }));
              setOutages((p) => ({ ...p, [vehicle.id]: false }));
            } catch (value) {
              if (value instanceof ApiError && value.status === 401)
                onExpired();
              setOutages((p) => ({ ...p, [vehicle.id]: true }));
              if (value instanceof ApiError && value.status === 403)
                setPermission(true);
            }
          }),
        );
      }
      setError("");
    } catch (value) {
      if (value instanceof ApiError && value.status === 401) onExpired();
      setError(message(value));
      if (value instanceof ApiError && value.status === 403)
        setPermission(true);
      setOutages((p) =>
        Object.fromEntries(Object.keys(p).map((key) => [key, true])),
      );
    } finally {
      polling.current = false;
      setLoading(false);
    }
  }, [view, onExpired]);
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void refresh();
    });
    const timer = setInterval(() => void refresh(), 5000),
      clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      active = false;
      clearInterval(timer);
      clearInterval(clock);
    };
  }, [refresh]);
  const freshness = (id: string) =>
    outages[id]
      ? ("LOST" as const)
      : gpsFreshness(live[id]?.position || null, now);
  const filtered = vehicles.filter(
    (v) =>
      `${v.plate_no} ${v.name || ""}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()) &&
      (!filter || freshness(v.id) === filter),
  );
  const driverName = (id: string) =>
    drivers.find(
      (d) =>
        d.active &&
        d.is_active &&
        d.vehicle_assignments.some(
          (a) => a.vehicle_id === id && a.status === "ACTIVE",
        ),
    )?.full_name || "Chưa có chuyến đang chạy phân tài xế";
  const positions = vehicles.flatMap((v) => {
    const p = live[v.id]?.position;
    return p?.valid && p.latitude !== null && p.longitude !== null
      ? [
          {
            latitude: p.latitude,
            longitude: p.longitude,
            selected: v.id === selected,
            stale: freshness(v.id) !== "NORMAL",
            label: `${v.plate_no} · ${freshness(v.id) === "NORMAL" ? "Vị trí hiện tại" : "Vị trí cuối ghi nhận"} · ${gpsLabels[freshness(v.id)]}`,
            details: `Tài xế: ${driverName(v.id)}\nTốc độ: ${p.speed_kmh?.toFixed(1) ?? "—"} km/h · Hướng: ${p.course ?? "—"}°\nACC: ${p.acc === null ? "Không xác định" : p.acc ? "Bật" : "Tắt"}\nĐộng cơ${freshness(v.id) === "NORMAL" ? "" : " (lần cuối)"}: ${engineLabels[p.engine_state]}\nGPS: ${time(p.gps_at)}\nServer nhận: ${time(p.server_received_at)}\nTọa độ: ${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}`,
          },
        ]
      : [];
  });
  async function saveVehicle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setActionError("");
    const f = new FormData(event.currentTarget),
      number = (key: string) => (f.get(key) ? Number(f.get(key)) : null);
    const data = {
      plate_no: f.get("plate_no"),
      name: f.get("name") || null,
      vehicle_type: f.get("vehicle_type") || null,
      status: f.get("status"),
      max_weight_kg: number("max_weight_kg"),
      max_volume_m3: number("max_volume_m3"),
      traccar_device_id: number("device"),
    };
    try {
      await api(
        editing ? `vehicles/${editing.id}` : "vehicles",
        editing ? "PUT" : "POST",
        data,
      );
      setFormOpen(false);
      setEditing(null);
      await refresh();
    } catch (value) {
      setActionError(message(value));
    } finally {
      setBusy(false);
    }
  }
  async function openVehicle(vehicle: Vehicle | null) {
    setEditing(vehicle);
    setFormOpen(true);
    setActionError("");
    try {
      setDevices(await api("gps/devices"));
    } catch (value) {
      setActionError(message(value));
    }
  }
  async function saveUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    setBusy(true);
    setActionError("");
    const f = new FormData(element);
    try {
      await api("users", "POST", {
        full_name: f.get("full_name"),
        email: f.get("email"),
        phone: f.get("phone") || null,
        password: f.get("password"),
        role: f.get("role"),
      });
      element.reset();
      await refresh();
    } catch (value) {
      setActionError(message(value));
    } finally {
      setBusy(false);
    }
  }
  async function toggleUser(item: User) {
    if (
      !confirm(
        `${item.is_active ? "Vô hiệu hóa" : "Kích hoạt"} ${item.full_name}? Thao tác được ghi nhật ký.`,
      )
    )
      return;
    setBusy(true);
    try {
      await api(`users/${item.id}`, "PATCH", { is_active: !item.is_active });
      await refresh();
    } catch (value) {
      setActionError(message(value));
    } finally {
      setBusy(false);
    }
  }
  async function removeVehicle(vehicle: Vehicle) {
    if (
      !confirm(
        `Xóa ${vehicle.plate_no}? Xe có dữ liệu vận hành sẽ không bị xóa. Thao tác được ghi nhật ký.`,
      )
    )
      return;
    setBusy(true);
    try {
      await api(`vehicles/${vehicle.id}`, "DELETE");
      await refresh();
    } catch (value) {
      setActionError(message(value));
    } finally {
      setBusy(false);
    }
  }
  async function loadHistory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHistoryBusy(true);
    setHistoryError("");
    setHistory(null);
    setDistance(null);
    const f = new FormData(event.currentTarget);
    try {
      const query = `?from=${encodeURIComponent(new Date(String(f.get("from"))).toISOString())}&to=${encodeURIComponent(new Date(String(f.get("to"))).toISOString())}`;
      const data = await api<History>(`vehicles/${selected}/history${query}`);
      setHistory(data);
      setPlayback(0);
      try {
        setDistance(
          (
            await api<{ distance_km: number | null }>(
              `vehicles/${selected}/odometer${query}`,
            )
          ).distance_km,
        );
      } catch {
        setHistoryError(
          "Đã tải hành trình; chưa lấy được báo cáo quãng đường Traccar.",
        );
      }
    } catch (value) {
      setHistoryError(message(value));
    } finally {
      setHistoryBusy(false);
    }
  }
  if (permission)
    return (
      <main>
        <h1>Không có quyền truy cập</h1>
        <p role="alert">Bạn không có quyền sử dụng màn hình này.</p>
      </main>
    );
  if (loading)
    return (
      <main aria-busy="true">
        <h1>Đang tải dữ liệu</h1>
        <div className="skeleton" role="status">
          Đang kết nối hệ thống…
        </div>
      </main>
    );
  return (
    <main className="fleet-workspace">
      <div className="page-heading">
        <div>
          <span className="eyebrow">XE & GPS</span>
          <h1>
            {view === "users"
              ? "Người dùng & phân quyền"
              : view === "vehicles"
                ? "Danh sách xe"
                : view === "history"
                  ? "Lịch sử hành trình"
                  : "Bản đồ xe trực tiếp"}
          </h1>
        </div>
        {user.role === "ADMIN" && view !== "users" && (
          <button onClick={() => void openVehicle(null)}>Thêm xe</button>
        )}
      </div>
      {error && (
        <div role="alert" className="error">
          {error}{" "}
          <button className="secondary" onClick={() => void refresh()}>
            Thử lại
          </button>
        </div>
      )}
      {actionError && (
        <div role="alert" className="error">
          {actionError}
        </div>
      )}
      {view === "users" ? (
        <>
          <section>
            <h2>Danh sách người dùng</h2>
            {!users.length ? (
              <p>Chưa có người dùng. Tạo tài khoản bên dưới.</p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Họ tên</th>
                      <th>Email</th>
                      <th>Vai trò</th>
                      <th>Trạng thái</th>
                      <th>Hành động</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((item) => (
                      <tr key={item.id}>
                        <td>{item.full_name}</td>
                        <td>{item.email}</td>
                        <td>{item.role}</td>
                        <td>
                          {item.is_active ? "Hoạt động" : "Ngừng hoạt động"}
                        </td>
                        <td>
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => void toggleUser(item)}
                          >
                            {item.is_active ? "Vô hiệu hóa" : "Kích hoạt"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section>
            <h2>Tạo người dùng</h2>
            <form onSubmit={saveUser} className="form-grid">
              <label>
                Họ tên *<input name="full_name" required />
              </label>
              <label>
                Email *<input name="email" type="email" required />
              </label>
              <label>
                Số điện thoại
                <input name="phone" />
              </label>
              <label>
                Vai trò *
                <select name="role">
                  <option>DRIVER</option>
                  <option>DISPATCHER</option>
                  <option>ADMIN</option>
                </select>
              </label>
              <label>
                Mật khẩu *
                <input
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  minLength={12}
                  required
                />
              </label>
              <button disabled={busy}>
                {busy ? "Đang lưu…" : "Tạo người dùng"}
              </button>
            </form>
          </section>
        </>
      ) : (
        <>
          {formOpen && (
            <section>
              <h2>{editing ? "Sửa xe" : "Thêm xe"}</h2>
              <form
                key={editing?.id || "new"}
                className="form-grid"
                onSubmit={saveVehicle}
              >
                <label>
                  Biển số *
                  <input
                    name="plate_no"
                    defaultValue={editing?.plate_no}
                    required
                  />
                </label>
                <label>
                  Tên xe
                  <input name="name" defaultValue={editing?.name || ""} />
                </label>
                <label>
                  Loại xe
                  <input
                    name="vehicle_type"
                    defaultValue={editing?.vehicle_type || ""}
                  />
                </label>
                <label>
                  Trạng thái *
                  <input
                    name="status"
                    defaultValue={editing?.status || "ACTIVE"}
                    required
                  />
                </label>
                <label>
                  Tải trọng (kg)
                  <input
                    name="max_weight_kg"
                    type="number"
                    min="0"
                    step="0.01"
                    defaultValue={editing?.max_weight_kg ?? ""}
                  />
                </label>
                <label>
                  Thể tích (m³)
                  <input
                    name="max_volume_m3"
                    type="number"
                    min="0"
                    step="0.001"
                    defaultValue={editing?.max_volume_m3 ?? ""}
                  />
                </label>
                <label>
                  Thiết bị GPS
                  <select
                    name="device"
                    defaultValue={editing?.traccar_device_id || ""}
                  >
                    <option value="">Chưa liên kết</option>
                    {devices.map((d) => (
                      <option value={d.id} key={d.id}>
                        {d.name} · {d.uniqueId}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="actions">
                  <button disabled={busy}>
                    {busy ? "Đang lưu…" : "Lưu xe"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setFormOpen(false)}
                  >
                    Hủy
                  </button>
                </div>
              </form>
            </section>
          )}
          {!vehicles.length && (
            <section>
              <h2>Chưa có xe</h2>
              <p>
                {user.role === "ADMIN"
                  ? "Thêm xe và liên kết thiết bị GPS Traccar để bắt đầu."
                  : "Liên hệ quản trị để thêm xe và thiết bị GPS."}
              </p>
            </section>
          )}
          <div className="live-layout">
            <section className="vehicle-panel">
              <h2>Xe trong hệ thống ({vehicles.length})</h2>
              <label>
                Tìm biển số / tên xe
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <label>
                Trạng thái GPS
                <select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {Object.entries(gpsLabels).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              {!filtered.length && vehicles.length > 0 && (
                <p>Không có xe phù hợp bộ lọc.</p>
              )}
              {filtered.map((vehicle) => {
                const p = live[vehicle.id]?.position,
                  state = freshness(vehicle.id);
                return (
                  <article
                    key={vehicle.id}
                    className={`vehicle-card ${selected === vehicle.id ? "selected" : ""}`}
                  >
                    <button
                      className="vehicle-select"
                      onClick={() => {
                        setSelected(vehicle.id);
                        setHistory(null);
                      }}
                    >
                      {vehicle.plate_no} · {vehicle.name || "Xe giao hàng"}
                    </button>
                    <span
                      className={`badge gps-${state.toLowerCase()}`}
                      data-testid={`gps-${vehicle.plate_no}`}
                    >
                      {state} · {gpsLabels[state]}
                    </span>
                    {outages[vehicle.id] && (
                      <p role="alert" className="error">
                        Không nhận được dữ liệu GPS từ hệ thống. Vị trí cuối
                        không phải dữ liệu trực tiếp.
                      </p>
                    )}
                    <p>
                      {!p
                        ? vehicle.traccar_device_id
                          ? "Chưa có dữ liệu GPS"
                          : "Chưa liên kết thiết bị GPS"
                        : state === "NORMAL"
                          ? "Vị trí hiện tại"
                          : "Vị trí cuối ghi nhận"}
                    </p>
                    {p && (
                      <dl>
                        <dt>Tài xế</dt>
                        <dd>{driverName(vehicle.id)}</dd>
                        <dt>Tọa độ</dt>
                        <dd>
                          {p.latitude?.toFixed(6) ?? "Không hợp lệ"},{" "}
                          {p.longitude?.toFixed(6) ?? "—"}
                        </dd>
                        <dt>Tốc độ / hướng</dt>
                        <dd>
                          {p.speed_kmh?.toFixed(1) ?? "—"} km/h ·{" "}
                          {p.course ?? "—"}°
                        </dd>
                        <dt>Động cơ {state !== "NORMAL" && "(lần cuối)"}</dt>
                        <dd>{engineLabels[p.engine_state]}</dd>
                        <dt>ACC</dt>
                        <dd>
                          {p.acc === null
                            ? "Không xác định"
                            : p.acc
                              ? "Bật"
                              : "Tắt"}
                        </dd>
                        <dt>GPS cập nhật</dt>
                        <dd>{time(p.gps_at)}</dd>
                        <dt>Server nhận</dt>
                        <dd>{time(p.server_received_at)}</dd>
                      </dl>
                    )}
                    <div className="actions">
                      <a
                        id={
                          vehicle.id === vehicles[0]?.id ? "history" : undefined
                        }
                        href={`/fleet/vehicles/${vehicle.id}/history`}
                      >
                        Lịch sử
                      </a>
                      {user.role === "ADMIN" && (
                        <>
                          <button
                            className="secondary"
                            onClick={() => void openVehicle(vehicle)}
                          >
                            Sửa
                          </button>
                          <button
                            className="danger"
                            disabled={busy}
                            onClick={() => void removeVehicle(vehicle)}
                          >
                            Xóa
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </section>
            <section className="map-panel">
              <h2>
                {view === "history" ? "Hành trình đã ghi nhận" : "Vị trí xe"}
              </h2>
              <Map
                points={
                  view === "history" && history
                    ? history.points
                        .slice(playback, playback + 1)
                        .flatMap((p) =>
                          p.valid && p.latitude !== null && p.longitude !== null
                            ? [
                                {
                                  latitude: p.latitude,
                                  longitude: p.longitude,
                                  label: `GPS: ${time(p.gps_at)}`,
                                  selected: true,
                                },
                              ]
                            : [],
                        )
                    : positions
                }
                segments={
                  view === "history" && history
                    ? history.segments.map((s) =>
                        s.flatMap((p) =>
                          p.latitude !== null && p.longitude !== null
                            ? [
                                {
                                  latitude: p.latitude,
                                  longitude: p.longitude,
                                  label: "Hành trình",
                                },
                              ]
                            : [],
                        ),
                      )
                    : []
                }
              />
              <p className="map-caption">
                Marker nét đứt: vị trí cuối ghi nhận. Luôn kiểm tra thời điểm
                GPS trước khi điều phối.
              </p>
              {view === "history" && (
                <>
                  <form
                    ref={historyForm}
                    className="form-grid"
                    onSubmit={loadHistory}
                  >
                    <label>
                      Từ *<input type="datetime-local" name="from" required />
                    </label>
                    <label>
                      Đến *<input type="datetime-local" name="to" required />
                    </label>
                    <button disabled={historyBusy || !selected}>
                      {historyBusy ? "Đang tải…" : "Xem hành trình"}
                    </button>
                  </form>
                  {historyError && (
                    <p role="alert" className="error">
                      {historyError}{" "}
                      <button
                        className="secondary"
                        disabled={historyBusy}
                        onClick={() => historyForm.current?.requestSubmit()}
                      >
                        Thử lại
                      </button>
                    </p>
                  )}
                  {history && (
                    <>
                      <p>
                        {history.points.length
                          ? `${history.points.length} bản tin GPS`
                          : "Không có dữ liệu GPS trong khoảng đã chọn."}{" "}
                        · Quãng đường Traccar:{" "}
                        {distance === null
                          ? "Chưa có báo cáo"
                          : `${distance.toFixed(2)} km`}
                      </p>
                      {history.points.length > 0 && (
                        <label>
                          Playback —{" "}
                          {time(history.points[playback]?.gps_at || null)}
                          <input
                            type="range"
                            min="0"
                            max={history.points.length - 1}
                            value={playback}
                            onChange={(e) =>
                              setPlayback(Number(e.target.value))
                            }
                          />
                        </label>
                      )}
                      {history.gaps.length > 0 && (
                        <p className="warning" role="status">
                          Có {history.gaps.length} đoạn thiếu/không hợp lệ GPS;
                          không nối đường qua các đoạn này.
                        </p>
                      )}
                      <h2>Điểm dừng</h2>
                      {!history.stops.length ? (
                        <p>Chưa xác định được điểm dừng từ dữ liệu hợp lệ.</p>
                      ) : (
                        <ul>
                          {history.stops.map((stop, index) => (
                            <li key={index}>
                              {engineLabels[stop.engine_state]} ·{" "}
                              {time(stop.started_at)} → {time(stop.ended_at)} ·{" "}
                              {Math.round(stop.duration_seconds)} giây (theo bản
                              tin quan sát)
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                </>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  );
}
