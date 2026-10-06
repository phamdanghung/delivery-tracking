"use client";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import FleetMap from "../fleet/map";
import { commitmentLabels, datetimePayload, showTime } from "./helpers";

type Point = { latitude: number; longitude: number };
type Trip = {
  id: string;
  status: string;
  plate_no: string;
  driver_name: string;
  start: Point | null;
  end: Point | null;
  stops: { id: string; recipient_name: string; delivery_id: string }[];
};
type Config = {
  configured: boolean;
  message: string | null;
  fixed_time_tolerance_seconds: number;
  default_service_seconds: number;
};
type Plan = {
  id: string;
  planned_departure_at: string;
  distance_m: number;
  duration_s: number;
  geometry: { coordinates: [number, number][] };
  warnings: string[];
  time_feasible: boolean;
  approval_allowed: boolean;
  approved: boolean;
  stale: boolean;
  stops: {
    stop_id: string;
    delivery_id: string;
    sequence_no: number;
    recipient_name: string;
    address_text: string;
    latitude: number;
    longitude: number;
    arrival_at: string;
    window_start: string | null;
    window_end: string;
    commitment_type: string;
    service_seconds: number;
    violation_seconds: number;
    violation: string | null;
  }[];
};
type Call = <T>(path: string, method?: string, data?: unknown) => Promise<T>;
const notifyExpired = (error: unknown, callback: (error: unknown) => void) => {
  if (error instanceof Error && "status" in error && error.status === 401)
    callback(error);
};
const toInput = (value: string) =>
  new Date(new Date(value).getTime() + 7 * 3600000).toISOString().slice(0, 16);

export default function TripOptimization({
  trip,
  api,
  onError,
}: {
  trip: Trip;
  api: Call;
  onError: (error: unknown) => void;
}) {
  const [config, setConfig] = useState<Config | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [departure, setDeparture] = useState("");
  const [service, setService] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState("");
  const [changed, setChanged] = useState(false);
  const [revision, setRevision] = useState(0);
  const hydratedTrip = useRef<string | null>(null);
  const form = useRef<HTMLFormElement | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Config>("routing/config"),
      api<Plan>(`trips/${trip.id}/optimization`).catch((error: unknown) => {
        if (error instanceof Error && "status" in error && error.status === 409)
          return null;
        throw error;
      }),
    ])
      .then(([settings, result]) => {
        if (!active) return;
        setConfig(settings);
        setPlan(result);
        if (result && hydratedTrip.current !== trip.id) {
          setDeparture(toInput(result.planned_departure_at));
          setService(
            Object.fromEntries(
              result.stops.map((s) => [
                s.stop_id,
                String(s.service_seconds / 60),
              ]),
            ),
          );
        }
        hydratedTrip.current = trip.id;
        setLoading(false);
      })
      .catch((value: unknown) => {
        if (active) {
          setError(
            value instanceof Error ? value.message : "Không thể tải kết quả",
          );
          notifyExpired(value, onError);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [trip.id, api, onError, revision]);
  useEffect(() => {
    if (!busy) return;
    const timer = setTimeout(() => setSlow(true), 10000);
    return () => clearTimeout(timer);
  }, [busy]);
  async function optimize(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const confirmedDeparture = String(fields.get("planned_departure_at") || "");
    const enteredServices = Object.fromEntries(
      trip.stops.map((s) => [
        s.id,
        String(fields.get(`service_${s.id}`) || ""),
      ]),
    );
    setDeparture(confirmedDeparture);
    setService(enteredServices);
    setBusy(true);
    setSlow(false);
    setError("");
    try {
      const overrides: Record<string, number> = {};
      for (const [id, value] of Object.entries(enteredServices)) {
        if (value === "") continue;
        const seconds = Number(value) * 60;
        if (!Number.isInteger(seconds) || seconds < 0)
          throw new Error(
            "Thời gian phục vụ phải quy đổi thành số giây nguyên không âm",
          );
        overrides[id] = seconds;
      }
      const result = await api<Plan>(`trips/${trip.id}/optimize`, "POST", {
        planned_departure_at: datetimePayload(confirmedDeparture),
        service_seconds: overrides,
      });
      setPlan(result);
      setChanged(false);
    } catch (value) {
      setChanged(true);
      setError(
        value instanceof Error ? value.message : "Không tối ưu được tuyến",
      );
      notifyExpired(value, onError);
    } finally {
      setBusy(false);
    }
  }
  async function approve() {
    if (!plan) return;
    const fields = form.current ? new FormData(form.current) : null;
    const unsaved =
      !fields ||
      fields.get("planned_departure_at") !==
        toInput(plan.planned_departure_at) ||
      plan.stops.some((s) => {
        const value = fields.get(`service_${s.stop_id}`);
        return (
          (value === ""
            ? config?.default_service_seconds
            : Number(value) * 60) !== s.service_seconds
        );
      });
    if (unsaved) {
      setDeparture(String(fields?.get("planned_departure_at") || ""));
      setService(
        Object.fromEntries(
          trip.stops.map((s) => [
            s.id,
            String(fields?.get(`service_${s.id}`) || ""),
          ]),
        ),
      );
      setChanged(true);
      setError(
        "Giờ xuất phát/service đã thay đổi; cần tối ưu lại trước khi duyệt.",
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`trips/${trip.id}/approve`, "POST", { plan_id: plan.id });
      setPlan({ ...plan, approved: true, approval_allowed: false });
    } catch (value) {
      setChanged(true);
      setError(
        value instanceof Error ? value.message : "Không duyệt được chuyến",
      );
      notifyExpired(value, onError);
    } finally {
      setBusy(false);
    }
  }
  const points = [
    ...(trip.start
      ? [
          {
            ...trip.start,
            label: "Điểm đầu",
            details: "Điểm đầu chuyến đã chọn",
          },
        ]
      : []),
    ...(plan?.stops.map((s) => ({
      latitude: s.latitude,
      longitude: s.longitude,
      label: String(s.sequence_no),
      numbered: true,
      stale: !!s.violation,
      details: `${s.recipient_name}\n${s.address_text}\nETA: ${showTime(s.arrival_at)}`,
    })) || []),
    ...(trip.end ? [{ ...trip.end, label: "Điểm cuối" }] : []),
  ];
  const segments = plan
    ? [
        plan.geometry.coordinates.map(([longitude, latitude]) => ({
          longitude,
          latitude,
          label: "",
        })),
      ]
    : [];
  return (
    <>
      <p>
        <Link href={`/trips/${trip.id}`}>← Chi tiết chuyến</Link> ·{" "}
        {trip.plate_no} · {trip.driver_name}
      </p>
      {loading && <p role="status">Đang tải cấu hình và kết quả tuyến…</p>}
      {error && (
        <div className="error" role="alert">
          {error}{" "}
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              setError("");
              setRevision((n) => n + 1);
            }}
          >
            Tải lại
          </button>
        </div>
      )}
      {!loading && (
        <div className="route-workspace">
          <section className="card route-map">
            <h2>Bản đồ tuyến giao</h2>
            <FleetMap points={points} segments={segments} />
            <p className="muted">
              Tuyến đường OSRM self-host · Dữ liệu © OpenStreetMap contributors
              / BBBike, ODbL.
            </p>
            {!plan && (
              <p>
                Chưa có kết quả tối ưu. Nhập và xác nhận giờ xuất phát để chạy.
              </p>
            )}
          </section>
          <section className="card route-summary">
            <h2>Tối ưu và duyệt chuyến</h2>
            {!config?.configured && (
              <p className="error" role="alert">
                {config?.message || "Thiếu cấu hình routing"}
              </p>
            )}
            <form ref={form} onSubmit={optimize}>
              <label>
                Giờ xuất phát dự kiến (UTC+07) *
                <input
                  type="datetime-local"
                  name="planned_departure_at"
                  required
                  value={departure}
                  disabled={busy || plan?.approved || trip.status !== "DRAFT"}
                  onChange={(e) => {
                    setDeparture(e.target.value);
                    setChanged(true);
                  }}
                />
              </label>
              <p className="muted">
                Nhấn tối ưu để xác nhận và lưu giờ xuất phát. Giờ cố định có
                dung sai ±{(config?.fixed_time_tolerance_seconds || 0) / 60}{" "}
                phút; các khung giờ/mốc hạn giữ nguyên.
              </p>
              <details>
                <summary>Thời gian phục vụ từng điểm (phút)</summary>
                {trip.stops.map((s) => (
                  <label key={s.id}>
                    {s.recipient_name}
                    <input
                      type="number"
                      name={`service_${s.id}`}
                      min="0"
                      step="0.05"
                      value={service[s.id] ?? ""}
                      placeholder={String(
                        (config?.default_service_seconds || 0) / 60,
                      )}
                      disabled={
                        busy || plan?.approved || trip.status !== "DRAFT"
                      }
                      onChange={(e) => {
                        setService({ ...service, [s.id]: e.target.value });
                        setChanged(true);
                      }}
                    />
                  </label>
                ))}
              </details>
              <button
                className="primary"
                disabled={
                  busy ||
                  !config?.configured ||
                  plan?.approved ||
                  trip.status !== "DRAFT"
                }
              >
                {busy
                  ? "Đang xử lý…"
                  : plan
                    ? "Tối ưu lại tuyến"
                    : "Xác nhận giờ và tối ưu tuyến"}
              </button>
            </form>
            {slow && busy && (
              <p role="status">
                Hệ thống đang xử lý tuyến. Vui lòng chờ kết quả.
              </p>
            )}
            {plan && (
              <>
                <p>
                  <strong>{(plan.distance_m / 1000).toFixed(2)} km</strong> ·{" "}
                  {Math.ceil(plan.duration_s / 60)} phút (gồm chờ/phục vụ)
                </p>
                {plan.warnings.map((w) => (
                  <p className="warning" key={w}>
                    {w}
                  </p>
                ))}
                {!plan.time_feasible && (
                  <p className="error" role="alert">
                    Vi phạm giờ hẹn: chưa được duyệt/xuất. Điều chỉnh dữ liệu và
                    chạy tối ưu lại.
                  </p>
                )}
                {(plan.stale || changed) && (
                  <p className="warning">
                    Dữ liệu/kết quả đã thay đổi. Cần tối ưu lại trước khi duyệt.
                  </p>
                )}
                <ol className="timeline">
                  {plan.stops.map((s) => (
                    <li key={s.stop_id}>
                      <Link href={`/deliveries/${s.delivery_id}`}>
                        {s.sequence_no}. {s.recipient_name}
                      </Link>
                      <p>{s.address_text}</p>
                      <p>
                        {commitmentLabels[s.commitment_type]}:{" "}
                        {s.window_start
                          ? `${showTime(s.window_start)} – `
                          : "Trước "}
                        {showTime(s.window_end)}
                      </p>
                      <p>
                        ETA: {showTime(s.arrival_at)} · phục vụ{" "}
                        {s.service_seconds / 60} phút
                      </p>
                      <span className={s.violation ? "error" : "success"}>
                        {s.violation
                          ? `${s.violation === "EARLY" ? "Sớm" : "Trễ"} ${Math.ceil(s.violation_seconds / 60)} phút`
                          : "Đúng hẹn"}
                      </span>
                    </li>
                  ))}
                </ol>
                {plan.approved ? (
                  <p className="success" role="status">
                    Đã duyệt/xuất chuyến.
                  </p>
                ) : (
                  <button
                    className="primary"
                    type="button"
                    disabled={
                      busy || changed || !plan.approval_allowed || plan.stale
                    }
                    onClick={approve}
                  >
                    Duyệt và xuất chuyến
                  </button>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </>
  );
}
