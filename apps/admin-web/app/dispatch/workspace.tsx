"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import TripOptimization from "./optimization";
import {
  commitmentLabels,
  datetimePayload,
  day,
  showTime,
  statusLabels,
  zaloSuggestions,
} from "./helpers";

type Call = <T>(path: string, method?: string, data?: unknown) => Promise<T>;
type Delivery = {
  id: string;
  code: string;
  recipient_name: string;
  recipient_phone: string;
  address_text: string;
  commitment_type: string;
  scheduled_date: string;
  appointment_at: string | null;
  window_start: string | null;
  window_end: string | null;
  deadline_at: string | null;
  latitude: number | null;
  longitude: number | null;
  weight_kg: number | null;
  volume_m3: number | null;
  notes: string | null;
  status: string;
  trip_id: string | null;
  plate_no: string | null;
  driver_name: string | null;
  eta_at: string | null;
};
type Event = {
  id: string;
  from_status: string | null;
  to_status: string;
  event_time: string;
  reason: string | null;
  actor_name: string;
  source: string;
  request_id: string;
};
type Proposal = {
  id: string;
  proposer_name: string;
  commitment_type: string;
  scheduled_date: string;
  appointment_at: string | null;
  window_start: string | null;
  window_end: string | null;
  deadline_at: string | null;
  confirmed_at: string | null;
};
type Detail = {
  delivery: Delivery;
  events: Event[];
  reschedule_proposals: Proposal[];
  audit: {
    action: string;
    created_at: string;
    actor_user_id: string;
    reason: string | null;
  }[];
};
type Vehicle = {
  id: string;
  plate_no: string;
  status: string;
  max_weight_kg: number | null;
  max_volume_m3: number | null;
};
type Driver = {
  id: string;
  full_name: string;
  active: boolean;
  is_active: boolean;
};
type Point = { latitude: number; longitude: number };
type Trip = {
  id: string;
  trip_date: string;
  plate_no: string;
  driver_name: string;
  status: string;
  weight_kg: number;
  volume_m3: number;
  warnings: string[];
  start: Point;
  end: Point;
  stops: {
    id: string;
    delivery_id: string;
    code: string;
    sequence_no: number;
    recipient_name: string;
    commitment_type: string;
    appointment_at: string | null;
    window_start: string | null;
    window_end: string | null;
    deadline_at: string | null;
    status: string;
    eta_at: string | null;
  }[];
};
export type DispatchView =
  | "list"
  | "form"
  | "detail"
  | "trips"
  | "trip-form"
  | "trip-detail"
  | "optimization";
const msg = (error: unknown) =>
  error instanceof Error ? error.message : "Không kết nối được hệ thống";
const inputTime = (iso: string | null) =>
  iso
    ? new Date(new Date(iso).getTime() + 7 * 3600000).toISOString().slice(0, 16)
    : "";
function commitmentText(item: {
  commitment_type: string;
  appointment_at: string | null;
  window_start: string | null;
  window_end: string | null;
  deadline_at: string | null;
}) {
  return item.commitment_type === "TIME_WINDOW"
    ? `${showTime(item.window_start)} – ${showTime(item.window_end)}`
    : `${commitmentLabels[item.commitment_type] || "Chưa có hẹn"}: ${showTime(item.appointment_at || item.deadline_at)}`;
}
function Badge({ status }: { status: string }) {
  const color =
    status === "DELIVERED"
      ? "NORMAL"
      : status === "FAILED"
        ? "LOST"
        : status === "RESCHEDULED"
          ? "STALE"
          : "";
  return (
    <span className={`badge ${color}`}>{statusLabels[status] || status}</span>
  );
}
const amount = (form: FormData, key: string) =>
  form.get(key) === "" ? null : Number(form.get(key));
function commitment(form: FormData) {
  const kind = String(form.get("commitment_type"));
  return {
    commitment_type: kind,
    scheduled_date: form.get("scheduled_date"),
    appointment_at:
      kind === "FIXED_TIME"
        ? datetimePayload(String(form.get("appointment_at")))
        : null,
    window_start:
      kind === "TIME_WINDOW"
        ? datetimePayload(String(form.get("window_start")))
        : null,
    window_end:
      kind === "TIME_WINDOW"
        ? datetimePayload(String(form.get("window_end")))
        : null,
    deadline_at:
      kind === "BEFORE_DEADLINE"
        ? datetimePayload(String(form.get("deadline_at")))
        : null,
  };
}

export default function DispatchWorkspace({
  api,
  view = "list",
  entityId,
  onExpired,
}: {
  api: Call;
  view?: DispatchView;
  entityId?: string;
  onExpired: () => void;
}) {
  const router = useRouter();
  const [orders, setOrders] = useState<Delivery[]>([]),
    [trips, setTrips] = useState<Trip[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [drivers, setDrivers] = useState<Driver[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null),
    [trip, setTrip] = useState<Trip | null>(null);
  const [config, setConfig] = useState<{
    company: Point | null;
    message: string | null;
  }>({ company: null, message: null });
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [date, setDate] = useState(() => {
      const requested =
        view === "trip-form" && typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("date")
          : null;
      return requested && /^\d{4}-\d{2}-\d{2}$/.test(requested)
        ? requested
        : day();
    }),
    [status, setStatus] = useState(""),
    [search, setSearch] = useState("");
  const [vehicleFilter, setVehicleFilter] = useState(""),
    [driverFilter, setDriverFilter] = useState("");
  const [selected, setSelected] = useState<string[]>([]),
    [revision, setRevision] = useState(0);
  const failure = useCallback(
    (value: unknown) => {
      if (value instanceof Error && "status" in value && value.status === 401)
        onExpired();
      else setError(msg(value));
    },
    [onExpired],
  );
  useEffect(() => {
    let alive = true;
    const params = new URLSearchParams({
      scheduled_date: date,
      search,
      limit: "200",
    });
    if (status) params.set("status", status);
    if (vehicleFilter) params.set("vehicle_id", vehicleFilter);
    if (driverFilter) params.set("driver_id", driverFilter);
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [v, d] = await Promise.all([
          api<Vehicle[]>("vehicles"),
          api<Driver[]>("drivers"),
        ]);
        if (!alive) return;
        setVehicles(v);
        setDrivers(d);
        if (view === "detail" || (view === "form" && entityId)) {
          const result = await api<Detail>(`deliveries/${entityId}`);
          if (alive) setDetail(result);
        } else if (view === "trip-detail" || view === "optimization") {
          const result = await api<Trip>(`trips/${entityId}`);
          if (alive) setTrip(result);
        } else if (view === "trips") {
          const result = await api<Trip[]>(`trips?trip_date=${date}`);
          if (alive) setTrips(result);
        } else if (view === "trip-form") {
          const [items, settings] = await Promise.all([
            api<Delivery[]>(`deliveries?scheduled_date=${date}&limit=200`),
            api<{ company: Point | null; message: string | null }>(
              "trips/config",
            ),
          ]);
          if (alive) {
            setOrders(
              items.filter((x) =>
                ["CREATED", "RESCHEDULED"].includes(x.status),
              ),
            );
            setConfig(settings);
          }
        } else if (view === "list") {
          const result = await api<Delivery[]>(`deliveries?${params}`);
          if (alive) setOrders(result);
        }
      } catch (value) {
        if (alive) failure(value);
      } finally {
        if (alive) setLoading(false);
      }
    };
    void load();
    return () => {
      alive = false;
    };
  }, [
    api,
    view,
    entityId,
    date,
    status,
    search,
    vehicleFilter,
    driverFilter,
    revision,
    failure,
  ]);
  async function mutate(path: string, payload: unknown, method = "POST") {
    setBusy(true);
    setError("");
    try {
      await api(path, method, payload);
      setRevision((x) => x + 1);
    } catch (value) {
      failure(value);
    } finally {
      setBusy(false);
    }
  }
  const heading = {
    list: "Đơn giao",
    form: entityId ? "Sửa đơn giao" : "Tạo đơn giao",
    detail: "Chi tiết đơn",
    trips: "Chuyến giao",
    "trip-form": "Lập chuyến nháp",
    "trip-detail": "Chi tiết chuyến",
    optimization: "Tối ưu tuyến",
  }[view];
  return (
    <main className="fleet-workspace dispatch-workspace">
      <div className="page-heading">
        <div>
          <span className="eyebrow">ĐIỀU PHỐI GIAO HÀNG</span>
          <h1>{heading}</h1>
        </div>
        {view === "list" && (
          <Link className="button-link" href="/deliveries/new">
            Tạo đơn
          </Link>
        )}
        {view === "trips" && (
          <Link className="button-link" href="/trips/new">
            Lập chuyến nháp
          </Link>
        )}
      </div>
      {error && (
        <div className="error" role="alert">
          {error}{" "}
          <button
            className="secondary"
            onClick={() => {
              if (view === "form")
                document
                  .querySelector<HTMLFormElement>("#order-form")
                  ?.requestSubmit();
              else if (view === "trip-form")
                document
                  .querySelector<HTMLFormElement>("#trip-form")
                  ?.requestSubmit();
              else setRevision((x) => x + 1);
            }}
          >
            Thử lại
          </button>
        </div>
      )}
      {loading && (
        <div className="skeleton" role="status" aria-busy="true">
          Đang tải dữ liệu…
        </div>
      )}
      {view === "list" && (
        <>
          <section className="card">
            <div className="form-grid">
              <label>
                Ngày giao
                <input
                  type="date"
                  value={date}
                  onChange={(e) => {
                    setDate(e.target.value);
                    setSelected([]);
                  }}
                />
              </label>
              <label>
                Trạng thái
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {Object.keys(statusLabels)
                    .slice(0, 10)
                    .map((x) => (
                      <option key={x} value={x}>
                        {statusLabels[x]}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Tìm khách / SĐT / mã
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <label>
                Xe
                <select
                  value={vehicleFilter}
                  onChange={(e) => setVehicleFilter(e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.plate_no}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Tài xế
                <select
                  value={driverFilter}
                  onChange={(e) => setDriverFilter(e.target.value)}
                >
                  <option value="">Tất cả</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Đúng giờ / trễ
                <select disabled aria-describedby="eta-note">
                  <option>Chưa có dữ liệu ETA</option>
                </select>
              </label>
            </div>
            <p id="eta-note" className="muted">
              Đánh giá đúng/trễ sẽ có khi chuyến được tối ưu ở M3.
            </p>
            {selected.length > 0 && (
              <Link
                className="button-link"
                href={`/trips/new?date=${date}&deliveries=${selected.join(",")}`}
              >
                Tạo chuyến từ {selected.length} đơn đã chọn
              </Link>
            )}
          </section>
          <section className="card">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Chọn</th>
                    <th>Mã đơn</th>
                    <th>Người nhận</th>
                    <th>Địa chỉ</th>
                    <th>Cam kết</th>
                    <th>Chuyến / xe</th>
                    <th>ETA / kết quả</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Chọn ${item.code}`}
                          disabled={
                            !["CREATED", "RESCHEDULED"].includes(item.status)
                          }
                          checked={selected.includes(item.id)}
                          onChange={(e) =>
                            setSelected((prev) =>
                              e.target.checked
                                ? [...prev, item.id]
                                : prev.filter((x) => x !== item.id),
                            )
                          }
                        />
                      </td>
                      <td>
                        <Link href={`/deliveries/${item.id}`}>{item.code}</Link>
                      </td>
                      <td>
                        {item.recipient_name}
                        <br />
                        <small>{item.recipient_phone}</small>
                      </td>
                      <td>{item.address_text}</td>
                      <td>{commitmentText(item)}</td>
                      <td>
                        {item.trip_id ? (
                          <Link href={`/trips/${item.trip_id}`}>
                            {item.plate_no} / {item.driver_name}
                          </Link>
                        ) : (
                          "Chưa lập chuyến"
                        )}
                      </td>
                      <td>
                        {item.eta_at
                          ? showTime(item.eta_at)
                          : ["DELIVERED", "FAILED", "CANCELLED"].includes(
                                item.status,
                              )
                            ? statusLabels[item.status]
                            : "Chưa có ETA"}
                      </td>
                      <td>
                        <Badge status={item.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!orders.length && (
              <div className="empty">
                <h2>Chưa có đơn phù hợp</h2>
                <p>Đổi bộ lọc hoặc tạo đơn giao mới.</p>
                <Link href="/deliveries/new">Tạo đơn</Link>
              </div>
            )}
            {orders.length === 200 && (
              <p className="warning">
                Đang hiển thị 200 đơn đầu; hãy thu hẹp bộ lọc.
              </p>
            )}
          </section>
        </>
      )}
      {!loading && view === "form" && (!entityId || detail) && (
        <OrderForm
          key={entityId || "new"}
          item={detail?.delivery}
          busy={busy}
          onSubmit={async (data) => {
            setBusy(true);
            setError("");
            try {
              const result = await api<Delivery>(
                entityId ? `deliveries/${entityId}` : "deliveries",
                entityId ? "PUT" : "POST",
                data,
              );
              router.push(`/deliveries/${result.id}`);
            } catch (value) {
              failure(value);
            } finally {
              setBusy(false);
            }
          }}
        />
      )}
      {!loading && view === "detail" && detail && (
        <>
          <section className="card">
            <h2>
              {detail.delivery.code} <Badge status={detail.delivery.status} />
            </h2>
            <p>
              {detail.delivery.recipient_name} ·{" "}
              {detail.delivery.recipient_phone}
            </p>
            <p>{detail.delivery.address_text}</p>
            <p>
              {commitmentText(detail.delivery)} · Ngày giao:{" "}
              {detail.delivery.scheduled_date}
            </p>
            <p>
              {detail.delivery.weight_kg ?? "Chưa nhập"} kg ·{" "}
              {detail.delivery.volume_m3 ?? "Chưa nhập"} m³
            </p>
            <p>
              Tọa độ: {detail.delivery.latitude ?? "Chưa xác minh"},{" "}
              {detail.delivery.longitude ?? "Chưa xác minh"}
            </p>
            <p>{detail.delivery.notes}</p>
            {["CREATED", "RESCHEDULED"].includes(detail.delivery.status) && (
              <Link href={`/deliveries/${entityId}/edit`}>Sửa thông tin</Link>
            )}
            {["CREATED", "PLANNED", "ASSIGNED"].includes(
              detail.delivery.status,
            ) && (
              <ActionForm
                title="Hủy đơn"
                busy={busy}
                reasonRequired
                onSubmit={(reason) =>
                  mutate(`deliveries/${entityId}/status`, {
                    from_status: detail.delivery.status,
                    to_status: "CANCELLED",
                    reason,
                  })
                }
              />
            )}
            {["ARRIVED", "DELIVERING"].includes(detail.delivery.status) && (
              <>
                <ActionForm
                  title="Giao không thành công"
                  reasonRequired
                  busy={busy}
                  onSubmit={(reason) =>
                    mutate(`deliveries/${entityId}/status`, {
                      from_status: detail.delivery.status,
                      to_status: "FAILED",
                      reason,
                    })
                  }
                />
                {detail.delivery.status === "ARRIVED" && (
                  <ActionForm
                    title="Sửa Đã đến nhận sai → Đang đi giao (ghi nhật ký)"
                    busy={busy}
                    reasonRequired
                    onSubmit={(reason) => mutate(`deliveries/${entityId}/arrival-correction`, {
                      arrival_event_id: [...detail.events].reverse().find((e) => e.to_status === "ARRIVED")?.id,
                      reason,
                    })}
                  />
                )}
                {detail.delivery.status === "ARRIVED" && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      mutate(`deliveries/${entityId}/status`, {
                        from_status: "ARRIVED",
                        to_status: "DELIVERING",
                      })
                    }
                  >
                    Bắt đầu bàn giao
                  </button>
                )}
              </>
            )}
          </section>
          <section className="card">
            <h2>Timeline trạng thái</h2>
            <ol className="timeline">
              {detail.events.map((e) => (
                <li key={e.id}>
                  <strong>{statusLabels[e.to_status]}</strong> ·{" "}
                  {showTime(e.event_time)}
                  <p>
                    {e.actor_name || e.source} ·{" "}
                    {e.reason || "Không có ghi chú"}
                  </p>
                </li>
              ))}
            </ol>
          </section>
          <section className="card">
            <h2>Lịch giao lại</h2>
            {detail.reschedule_proposals.map((p) => (
              <article key={p.id}>
                <p>
                  {p.proposer_name} đề xuất: {commitmentText(p)} ·{" "}
                  {p.scheduled_date}
                </p>
                {p.confirmed_at ? (
                  <p>Đã xác nhận {showTime(p.confirmed_at)}</p>
                ) : (
                  <p>Chờ điều phối xác nhận — lịch chính chưa thay đổi</p>
                )}
                {!p.confirmed_at && detail.delivery.status === "FAILED" && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      mutate(`deliveries/${entityId}/reschedule`, {
                        proposal_id: p.id,
                      })
                    }
                  >
                    Xác nhận đề xuất
                  </button>
                )}
              </article>
            ))}
            {!detail.reschedule_proposals.length && (
              <p>Chưa có đề xuất từ tài xế.</p>
            )}
            {detail.delivery.status === "FAILED" && (
              <CommitmentForm
                busy={busy}
                onSubmit={(data) =>
                  mutate(`deliveries/${entityId}/reschedule`, {
                    commitment: data,
                  })
                }
              />
            )}
          </section>
          <section className="card">
            <h2>Ảnh POD</h2>
            <p>Chưa có ảnh được tải lên trong phạm vi M2.</p>
            <h2>Tracking link</h2>
            <p>Chưa phát hành link theo dõi khách hàng.</p>
          </section>
          <section className="card">
            <h2>Nhật ký thay đổi</h2>
            {detail.audit.map((a, i) => (
              <p key={i}>
                {a.action} · {showTime(a.created_at)} ·{" "}
                {a.reason || "Đã ghi người thao tác và dữ liệu trước/sau"}
              </p>
            ))}
          </section>
        </>
      )}
      {!loading && view === "trips" && (
        <>
          <section className="card">
            <label>
              Ngày chuyến
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
          </section>
          <section className="card">
            {trips.map((t) => (
              <article key={t.id}>
                <h2>
                  <Link href={`/trips/${t.id}`}>
                    {t.trip_date} · {t.plate_no}
                  </Link>{" "}
                  <Badge status={t.status} />
                </h2>
                <p>
                  {t.driver_name} · {t.stops.length} điểm · {t.weight_kg} kg /{" "}
                  {t.volume_m3} m³
                </p>
              </article>
            ))}
            {!trips.length && (
              <div className="empty">
                <h2>Chưa có chuyến</h2>
                <p>Chọn đơn để lập chuyến nháp.</p>
                <Link href="/trips/new">Lập chuyến nháp</Link>
              </div>
            )}
          </section>
        </>
      )}
      {!loading && view === "trip-form" && (
        <TripForm
          key={`${date}-${revision}`}
          orders={orders}
          vehicles={vehicles}
          drivers={drivers}
          date={date}
          onDate={setDate}
          config={config}
          busy={busy}
          onSubmit={async (data) => {
            setBusy(true);
            setError("");
            try {
              const result = await api<Trip>("trips", "POST", data);
              router.push(`/trips/${result.id}`);
            } catch (value) {
              failure(value);
            } finally {
              setBusy(false);
            }
          }}
        />
      )}
      {!loading && view === "trip-detail" && trip && (
        <>
          <section className="card">
            <h2>
              {trip.trip_date} · {trip.plate_no} <Badge status={trip.status} />
            </h2>
            <p>
              {trip.driver_name} · {trip.weight_kg} kg / {trip.volume_m3} m³
            </p>
            <p>
              Điểm đầu: {trip.start?.latitude}, {trip.start?.longitude} · Điểm
              cuối: {trip.end?.latitude}, {trip.end?.longitude}
            </p>
            {trip.warnings.map((w) => (
              <p className="warning" key={w}>
                {w}
              </p>
            ))}
            {trip.status === "DRAFT" && (
              <Link className="primary" href={`/trips/${trip.id}/optimize`}>
                Tối ưu tuyến và xem ETA trước khi duyệt
              </Link>
            )}
          </section>
          <section className="card">
            <h2>Các điểm giao theo thứ tự đã chọn</h2>
            <ol className="timeline">
              {trip.stops.map((s) => (
                <li key={s.id}>
                  <Link href={`/deliveries/${s.delivery_id}`}>
                    {s.code} · {s.recipient_name}
                  </Link>
                  <p>
                    {commitmentText(s)} · <Badge status={s.status} />
                  </p>
                  <p>ETA: {showTime(s.eta_at)}</p>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
      {!loading && view === "optimization" && trip && (
        <TripOptimization trip={trip} api={api} onError={failure} />
      )}
    </main>
  );
}

function TimeFields({
  item,
  kind,
  setKind,
}: {
  item?: Partial<Delivery>;
  kind: string;
  setKind: (kind: string) => void;
}) {
  return (
    <>
      <label>
        Ngày giao *
        <input
          name="scheduled_date"
          type="date"
          defaultValue={item?.scheduled_date || day()}
          required
        />
      </label>
      <label>
        Kiểu hẹn *
        <select
          name="commitment_type"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          {Object.entries(commitmentLabels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <p className="muted">Thời gian theo múi giờ công ty UTC+07.</p>
      {kind === "FIXED_TIME" && (
        <label>
          Giờ cố định *
          <input
            name="appointment_at"
            type="datetime-local"
            defaultValue={inputTime(item?.appointment_at || null)}
            required
          />
        </label>
      )}
      {kind === "TIME_WINDOW" && (
        <>
          <label>
            Từ *
            <input
              name="window_start"
              type="datetime-local"
              defaultValue={inputTime(item?.window_start || null)}
              required
            />
          </label>
          <label>
            Đến *
            <input
              name="window_end"
              type="datetime-local"
              defaultValue={inputTime(item?.window_end || null)}
              required
            />
          </label>
        </>
      )}
      {kind === "BEFORE_DEADLINE" && (
        <label>
          Giao trước *
          <input
            name="deadline_at"
            type="datetime-local"
            defaultValue={inputTime(item?.deadline_at || null)}
            required
          />
        </label>
      )}
    </>
  );
}
function OrderForm({
  item,
  busy,
  onSubmit,
}: {
  item?: Delivery;
  busy: boolean;
  onSubmit: (data: unknown) => Promise<void>;
}) {
  const [kind, setKind] = useState(item?.commitment_type || "TIME_WINDOW");
  const [draft, setDraft] = useState(""),
    [suggestions, setSuggestions] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setFeedback("");
    if (
      kind === "TIME_WINDOW" &&
      String(form.get("window_start")) > String(form.get("window_end"))
    ) {
      setFeedback("Khung giờ: thời điểm kết thúc phải sau hoặc bằng bắt đầu.");
      return;
    }
    const data = {
      ...commitment(form),
      ...Object.fromEntries(
        ["recipient_name", "recipient_phone", "address_text", "notes"].map(
          (k) => [k, form.get(k)],
        ),
      ),
      latitude: amount(form, "latitude"),
      longitude: amount(form, "longitude"),
      weight_kg: amount(form, "weight_kg"),
      volume_m3: amount(form, "volume_m3"),
    };
    if ((data.latitude === null) !== (data.longitude === null)) {
      setFeedback("Tọa độ: nhập đủ vĩ độ và kinh độ.");
      return;
    }
    await onSubmit(data);
  }
  return (
    <>
      <section className="card">
        <h2>Nháp Zalo</h2>
        <label>
          Nội dung nháp
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={5}
          />
        </label>
        <button
          className="secondary"
          type="button"
          onClick={() => {
            setSuggestions(zaloSuggestions(draft));
            setFeedback(
              "Đã điền gợi ý từ dòng có nhãn Khách, SĐT, Địa chỉ, Ghi chú. Kiểm tra và chỉnh lại trước khi lưu; chưa có đơn nào được tạo.",
            );
          }}
        >
          Tách thông tin
        </button>
      </section>
      <section className="card">
        <h2>Thông tin chuẩn</h2>
        <form id="order-form" onSubmit={submit}>
          {feedback && <p role="status">{feedback}</p>}
          <div className="form-grid">
            {[
              ["recipient_name", "Người nhận *"],
              ["recipient_phone", "SĐT *"],
              ["address_text", "Địa chỉ *"],
              ["notes", "Ghi chú"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  key={`${key}-${suggestions[key] || ""}`}
                  name={key}
                  defaultValue={
                    suggestions[key] ??
                    String(item?.[key as keyof Delivery] ?? "")
                  }
                  required={key !== "notes"}
                />
              </label>
            ))}
            <TimeFields item={item} kind={kind} setKind={setKind} />
            <label>
              Khối lượng (kg)
              <input
                name="weight_kg"
                type="number"
                min="0"
                step="0.01"
                defaultValue={item?.weight_kg ?? ""}
              />
            </label>
            <label>
              Thể tích (m³)
              <input
                name="volume_m3"
                type="number"
                min="0"
                step="0.001"
                defaultValue={item?.volume_m3 ?? ""}
              />
            </label>
            <label>
              Vĩ độ đã xác minh
              <input
                name="latitude"
                type="number"
                min="-90"
                max="90"
                step="any"
                defaultValue={item?.latitude ?? ""}
              />
            </label>
            <label>
              Kinh độ đã xác minh
              <input
                name="longitude"
                type="number"
                min="-180"
                max="180"
                step="any"
                defaultValue={item?.longitude ?? ""}
              />
            </label>
          </div>
          <p className="muted">
            Có thể lưu đơn chưa xác minh tọa độ; cần đủ tọa độ trước khi lập
            chuyến. Không tự geocode địa chỉ.
          </p>
          <div className="actions">
            <Link href={item ? `/deliveries/${item.id}` : "/deliveries"}>
              Hủy
            </Link>
            <button disabled={busy}>{busy ? "Đang lưu…" : "Lưu đơn"}</button>
          </div>
        </form>
      </section>
    </>
  );
}
function ActionForm({
  title,
  reasonRequired,
  busy,
  onSubmit,
}: {
  title: string;
  reasonRequired: boolean;
  busy: boolean;
  onSubmit: (reason: string) => Promise<void>;
}) {
  const [opened, setOpened] = useState(false);
  return (
    <div className="status-action">
      {!opened ? (
        <button
          className="danger"
          type="button"
          onClick={() => setOpened(true)}
        >
          {title}
        </button>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            await onSubmit(String(new FormData(e.currentTarget).get("reason")));
          }}
        >
          <p>
            Thao tác {title.toLocaleLowerCase("vi-VN")} sẽ được ghi nhật ký.
          </p>
          <label>
            Lý do *
            <input name="reason" required={reasonRequired} maxLength={2000} />
          </label>
          <button
            className="secondary"
            type="button"
            onClick={() => setOpened(false)}
          >
            Quay lại
          </button>{" "}
          <button className="danger" disabled={busy}>
            {busy
              ? "Đang xử lý…"
              : `Xác nhận ${title.toLocaleLowerCase("vi-VN")}`}
          </button>
        </form>
      )}
    </div>
  );
}
function CommitmentForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (data: unknown) => Promise<void>;
}) {
  const [kind, setKind] = useState("FIXED_TIME");
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        await onSubmit(commitment(new FormData(e.currentTarget)));
      }}
    >
      <h3>Điều phối xác nhận lịch mới</h3>
      <div className="form-grid">
        <TimeFields kind={kind} setKind={setKind} />
      </div>
      <p>
        Lịch mới có hiệu lực khi xác nhận; đơn quay lại danh sách chờ điều phối.
      </p>
      <button disabled={busy}>
        {busy ? "Đang xác nhận…" : "Xác nhận lịch giao lại"}
      </button>
    </form>
  );
}
function TripForm({
  orders,
  vehicles,
  drivers,
  date,
  onDate,
  config,
  busy,
  onSubmit,
}: {
  orders: Delivery[];
  vehicles: Vehicle[];
  drivers: Driver[];
  date: string;
  onDate: (value: string) => void;
  config: { company: Point | null; message: string | null };
  busy: boolean;
  onSubmit: (data: unknown) => Promise<void>;
}) {
  const [chosen, setChosen] = useState<string[]>(() => {
    const params = new URLSearchParams(
      typeof window === "undefined" ? "" : window.location.search,
    );
    return (params.get("deliveries") || "")
      .split(",")
      .filter((x) => orders.some((o) => o.id === x));
  });
  const [vehicleId, setVehicleId] = useState("");
  const picked = orders.filter((x) => chosen.includes(x.id)),
    vehicle = vehicles.find((x) => x.id === vehicleId);
  const kg = picked.reduce((sum, x) => sum + (x.weight_kg || 0), 0),
    volume = picked.reduce((sum, x) => sum + (x.volume_m3 || 0), 0);
  const over =
    vehicle &&
    ((vehicle.max_weight_kg !== null && kg > vehicle.max_weight_kg) ||
      (vehicle.max_volume_m3 !== null && volume > vehicle.max_volume_m3));
  return (
    <form
      id="trip-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        await onSubmit({
          trip_date: date,
          vehicle_id: vehicleId,
          driver_id: form.get("driver_id"),
          delivery_ids: chosen,
          start: {
            latitude: Number(form.get("start_lat")),
            longitude: Number(form.get("start_lon")),
          },
          end: {
            latitude: Number(form.get("end_lat")),
            longitude: Number(form.get("end_lon")),
          },
        });
      }}
    >
      <section className="card">
        <label>
          Ngày chuyến *
          <input
            type="date"
            value={date}
            required
            onChange={(e) => onDate(e.target.value)}
          />
        </label>
        <h2>Đơn chưa lập chuyến</h2>
        {orders.map((item) => (
          <label className="selection-row" key={item.id}>
            <input
              type="checkbox"
              checked={chosen.includes(item.id)}
              onChange={(e) =>
                setChosen((prev) =>
                  e.target.checked
                    ? [...prev, item.id]
                    : prev.filter((x) => x !== item.id),
                )
              }
            />
            {item.code} · {item.recipient_name} · {commitmentText(item)}
            {item.latitude === null && " — Chưa có tọa độ"}
          </label>
        ))}
        {!orders.length && (
          <p>
            Chưa có đơn chưa phân trong ngày này.{" "}
            <Link href="/deliveries/new">Tạo đơn</Link>
          </p>
        )}
      </section>
      <section className="card">
        <div className="form-grid">
          <label>
            Xe *
            <select
              value={vehicleId}
              onChange={(e) => setVehicleId(e.target.value)}
              required
            >
              <option value="">Chọn xe</option>
              {vehicles
                .filter((v) => v.status === "ACTIVE")
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate_no}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Tài xế *
            <select name="driver_id" required>
              <option value="">Chọn tài xế</option>
              {drivers
                .filter((d) => d.active && d.is_active)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name}
                  </option>
                ))}
            </select>
          </label>
        </div>
        <p>
          Tổng đã nhập: {kg} kg / {volume} m³ · Sức chứa xe:{" "}
          {vehicle?.max_weight_kg ?? "Chưa cấu hình"} kg /{" "}
          {vehicle?.max_volume_m3 ?? "Chưa cấu hình"} m³
        </p>
        {over && (
          <p className="warning" role="alert">
            Vượt tải trọng/thể tích — chỉ cảnh báo, vẫn được lưu chuyến.
          </p>
        )}
        {picked.some((x) => x.weight_kg === null || x.volume_m3 === null) && (
          <p className="warning">
            Có đơn chưa nhập kg/m³; chưa thể đánh giá đầy đủ tải.
          </p>
        )}
        {config.message && (
          <p className="warning" role="alert">
            {config.message}. Cần cấu hình hoặc nhập đủ điểm đầu/cuối thay thế
            trước khi lưu.
          </p>
        )}
        <h2>Điểm đầu / cuối</h2>
        <div className="form-grid">
          {[
            [
              "start_lat",
              "Điểm đầu — vĩ độ",
              config.company?.latitude,
              -90,
              90,
            ],
            [
              "start_lon",
              "Điểm đầu — kinh độ",
              config.company?.longitude,
              -180,
              180,
            ],
            ["end_lat", "Điểm cuối — vĩ độ", config.company?.latitude, -90, 90],
            [
              "end_lon",
              "Điểm cuối — kinh độ",
              config.company?.longitude,
              -180,
              180,
            ],
          ].map(([name, label, value, min, max]) => (
            <label key={String(name)}>
              {String(label)} *
              <input
                name={String(name)}
                type="number"
                step="any"
                min={Number(min)}
                max={Number(max)}
                defaultValue={value === undefined ? "" : Number(value)}
                required
              />
            </label>
          ))}
        </div>
        <p>
          Chỉ lưu chuyến nháp. Tối ưu/ETA và duyệt/xuất chuyến sẽ có sau M3.
        </p>
        <button disabled={busy || !chosen.length}>
          {busy ? "Đang lưu…" : "Lưu chuyến nháp"}
        </button>
      </section>
    </form>
  );
}
