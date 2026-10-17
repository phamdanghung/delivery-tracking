"use client";

import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";

type Call = <T>(path: string, method?: string, data?: unknown) => Promise<T>;
type Scalar = string | number | null;
type Row = Record<string, unknown>;
type Page = { total: number; offset: number; limit: number; items: Row[] };
type Group = "attempts" | "vehicles" | "financial/sources";
type Summary = { trips: number; attempts: number; failed_attempts: number; early: number; on_time: number; late: number; unknown: number; eligible_attempts: number; early_rate: Scalar; on_time_rate: Scalar; late_rate: Scalar };
type Financial = { total_fuel_liters: Scalar; total_fuel_cost: Scalar; total_trip_expense: Scalar; fuel_missing_amount: number; grand_total_reason: string; reconciliations: Row[]; excluded_reconciliations: Row[] };
const labels: Record<string, string> = { EARLY: "Đến sớm", ON_TIME: "Đúng hẹn", LATE: "Đến trễ", UNKNOWN: "Chưa đủ dữ liệu", VALID: "Đủ dữ liệu", PARTIAL: "Dữ liệu một phần", FIXED_TIME: "Giờ cố định", TIME_WINDOW: "Khung giờ", BEFORE_DEADLINE: "Trước hạn", FAILED: "Giao thất bại", DELIVERED: "Đã giao", VOIDED: "Đã hủy bản ghi", NOT_FINAL: "Chưa chốt", NOT_WHOLLY_IN_REPORT_PERIOD: "Kỳ đối soát không nằm trọn kỳ báo cáo", VERSION_MISSING: "Thiếu phiên bản" };
const text = (v: unknown) => v == null ? "Chưa xác định" : String(v);
const amount = (v: Scalar) => v == null ? "Chưa xác định" : Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const percent = (v: Scalar) => v == null ? "Chưa xác định" : `${(Number(v) * 100).toLocaleString("vi-VN", { maximumFractionDigits: 2 })}%`;
const stamp = (v: unknown) => v == null ? "Chưa xác định" : new Date(String(v)).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" });

function Table({ headers, children }: { headers: string[]; children: ReactNode }) {
  return <div className="table-wrap"><table><thead><tr>{headers.map(h => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
function Trace({ value }: { value: Row }) {
  return <details><summary>Nguồn & truy vết</summary><dl>{Object.entries(value).map(([key, v]) => <div key={key}><dt>{key}</dt><dd>{v == null ? "Chưa xác định" : typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>)}</dl></details>;
}

export default function ReportsWorkspace({ api, onExpired }: { api: Call; onExpired: () => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [financial, setFinancial] = useState<Financial | null>(null);
  const [page, setPage] = useState<Page | null>(null);
  const [group, setGroup] = useState<Group>("attempts");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const sequence = useRef(0);
  const [intervals, setIntervals] = useState<{ vehicle: string; page: Page } | null>(null);
  const [vehicles, setVehicles] = useState<{id: string; plate_no: string}[]>([]);
  const [vehicleError, setVehicleError] = useState("");
  useEffect(() => {
    let active = true;
    void api<{id: string; plate_no: string}[]>("vehicles").then(value => {
      if (active) setVehicles(value);
    }).catch(value => {
      if (!active) return;
      if (value instanceof Error && "status" in value && value.status === 401) onExpired();
      setVehicleError("Chưa tải được danh sách xe. Có thể xem tất cả xe hoặc tải lại trang để chọn xe.");
    });
    return () => { active = false; };
  }, [api, onExpired]);
  function failure(value: unknown) {
    if (value instanceof Error && "status" in value && value.status === 401) onExpired();
    setError(value instanceof Error ? value.message : "Không thể tải báo cáo");
  }
  async function load(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    const form = new FormData(event.currentTarget);
    const params = new URLSearchParams({ date_from: String(form.get("from")), date_to: String(form.get("to")) });
    if (form.get("vehicle")) params.set("vehicle_id", String(form.get("vehicle")).trim());
    const q = params.toString(), version = ++sequence.current;
    setBusy(true); setError(""); setSummary(null); setFinancial(null); setPage(null); setIntervals(null);
    try {
      const [s, f, p] = await Promise.all([
        api<Summary>(`reports/summary?${q}`), api<Financial>(`reports/financial?${q}`),
        api<Page>(`reports/attempts?${q}&limit=20`),
      ]);
      if (version !== sequence.current) return;
      setSummary(s); setFinancial(f); setPage(p); setGroup("attempts"); setQuery(q);
    } catch (value) { if (version === sequence.current) failure(value); }
    finally { if (version === sequence.current) setBusy(false); }
  }
  async function show(next: Group, offset = 0) {
    if (busy || !query) return;
    setBusy(true); setError(""); setPage(null); setIntervals(null); setGroup(next);
    try { setPage(await api<Page>(`reports/${next}?${query}&offset=${offset}&limit=${next === "vehicles" ? 5 : 20}`)); }
    catch (value) { failure(value); } finally { setBusy(false); }
  }
  async function traceVehicle(id: string, offset = 0) {
    setBusy(true); setError(""); setIntervals(null);
    try { setIntervals({ vehicle: id, page: await api<Page>(`reports/vehicles/${id}/intervals?${query}&offset=${offset}&limit=20`) }); }
    catch (value) { failure(value); } finally { setBusy(false); }
  }
  return <main className="fleet-workspace"><div className="page-heading"><h1>Báo cáo vận hành</h1></div>
    <p>Kỳ báo cáo theo múi giờ hệ thống (UTC+07:00). Đúng hẹn theo từng lượt giao và ngày chuyến; nhiên liệu theo ngày đổ. Dữ liệu thiếu không được thay bằng số 0.</p>
    <section><form onSubmit={load}>
      <label>Từ ngày<input type="date" name="from" required disabled={busy} /></label>
      <label>Đến ngày<input type="date" name="to" required disabled={busy} /></label>
      <label>Xe<select name="vehicle" disabled={busy}><option value="">Tất cả xe</option>{vehicles.map(v => <option key={v.id} value={v.id}>{v.plate_no}</option>)}</select></label>
      <button disabled={busy}>{busy ? "Đang tải…" : "Xem báo cáo"}</button>
    </form></section>
    {vehicleError && <p role="status">{vehicleError}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {busy && <p role="status">Đang xác minh dữ liệu báo cáo…</p>}
    {!summary && !busy && !error && <p>Chọn kỳ để xem báo cáo.</p>}
    {summary && <section><h2>Chuyến & đúng hẹn</h2><div className="kpi-grid">
      {[["Chuyến", summary.trips], ["Lượt giao", summary.attempts], ["Giao thất bại", summary.failed_attempts], ["Đúng hẹn", summary.on_time], ["Đến sớm", summary.early], ["Đến trễ", summary.late], ["Chưa đủ dữ liệu", summary.unknown]].map(([title, value]) => <article className="kpi-card" key={title}><span>{title}</span><strong>{value}</strong></article>)}
    </div><p>Đủ dữ liệu: {summary.eligible_attempts} lượt · Đúng hẹn {percent(summary.on_time_rate)} · Đến sớm {percent(summary.early_rate)} · Đến trễ {percent(summary.late_rate)}. UNKNOWN không nằm trong mẫu số.</p></section>}
    {financial && <section><h2>Nhiên liệu & chi phí chuyến</h2>
      <p>Nhiên liệu: {amount(financial.total_fuel_liters)} lít · Tiền nhiên liệu: {amount(financial.total_fuel_cost)} · Chi phí chuyến: {amount(financial.total_trip_expense)}.</p>
      {financial.fuel_missing_amount > 0 && <p role="status">{financial.fuel_missing_amount} lần đổ thiếu số tiền; tổng tiền nhiên liệu chưa xác định.</p>}
      <p>Không hiển thị tổng gộp: {financial.grand_total_reason}.</p>
      <h3>Đối soát FINAL — phiên bản hiện hành</h3>
      {!financial.reconciliations.length && <p>Chưa có kỳ FINAL nằm trọn khoảng báo cáo.</p>}
      {financial.reconciliations.map(r => <article key={text(r.version_id)}><p>Xe {text(r.vehicle_id)} · {stamp(r.from_at)} → {stamp(r.to_at)} · Phiên bản {text(r.version)} · Thực tế {text(r.actual_liters)} / dự kiến {text(r.expected_liters)} lít · Chênh lệch {text(r.variance_pct)}%</p><Trace value={r} /></article>)}
      {financial.excluded_reconciliations.map(r => <p key={text(r.reconciliation_id)}>Kỳ {text(r.reconciliation_id)}: {labels[text(r.reason)] ?? text(r.reason)}.</p>)}
    </section>}
    {summary && <section><div className="actions">{([ ["attempts", "Lượt giao"], ["vehicles", "Xe / km / giờ thực"], ["financial/sources", "Nguồn chi phí"] ] as const).map(([key,title]) => <button key={key} className="secondary" disabled={busy} aria-pressed={group === key} onClick={() => void show(key)}>{title}</button>)}</div>
      {page && <><p>{page.total} bản ghi · {page.offset + (page.items.length ? 1 : 0)}–{page.offset + page.items.length}</p>
        {!page.items.length ? <p>Không có dữ liệu trong kỳ hoặc trang này.</p> : group === "attempts" ? <Table headers={["Chuyến / đơn", "Lượt giao", "Phân loại", "ARRIVED", "Truy vết"]}>{page.items.map(r => <tr key={text(r.attempt_id)}><td><Link href={`/trips/${r.trip_id}`}>{text(r.trip_date)}</Link><br /><Link href={`/deliveries/${r.delivery_id}`}>{text(r.delivery_code)}</Link></td><td>{text(r.attempt_id)}<br />{labels[text(r.attempt_status)] ?? text(r.attempt_status)}</td><td><span className="badge">{labels[text(r.status)]}</span></td><td>{stamp(r.arrived_at)}</td><td><Trace value={r} /></td></tr>)}</Table>
          : group === "vehicles" ? <Table headers={["Xe", "Chuyến / lượt", "Km thực", "Giờ vận hành", "Chất lượng / nguồn"]}>{page.items.map(r => <tr key={text(r.vehicle_id)}><td>{text(r.plate_no)}</td><td>{text(r.trips)} / {text(r.attempts)}</td><td>{amount(r.distance_km as Scalar)}<br />{labels[text(r.distance_quality)]}</td><td>{amount(r.operating_hours as Scalar)}<br />{labels[text(r.hours_quality)]}</td><td><p>Coverage giờ: {text(r.hours_coverage_seconds)}s / {text(r.period_seconds)}s; km: {text(r.distance_coverage_seconds)}s.</p><Trace value={r} /><button className="secondary" disabled={busy} onClick={() => void traceVehicle(text(r.vehicle_id))}>Xem interval nguồn</button></td></tr>)}</Table>
          : <Table headers={["Nguồn / record", "Ngày nghiệp vụ", "Loại", "Lít / tiền", "Tính vào tổng"]}>{page.items.map(r => <tr key={`${r.source_table}-${r.record_id}`}><td>{text(r.source_table)}<br />{text(r.record_id)}<Trace value={r} /></td><td>{text(r.business_date)}</td><td>{text(r.category)}</td><td>{text(r.liters)} / {amount(r.amount as Scalar)}</td><td>{r.included ? "Có" : labels[text(r.exclusion_reason)] ?? text(r.exclusion_reason)}</td></tr>)}</Table>}
        <div className="actions"><button className="secondary" disabled={busy || page.offset === 0} onClick={() => void show(group, Math.max(0,page.offset-page.limit))}>Trang trước</button><button className="secondary" disabled={busy || page.offset+page.limit >= page.total} onClick={() => void show(group,page.offset+page.limit)}>Trang tiếp</button></div>
      </>}
      {intervals && <article><h3>Interval Traccar · xe {intervals.vehicle}</h3>{!intervals.page.items.length && <p>Chưa có interval hợp lệ.</p>}{intervals.page.items.map(r => <Trace key={`${r.from_at}-${r.to_at}`} value={r} />)}<button className="secondary" disabled={busy || intervals.page.offset === 0} onClick={() => void traceVehicle(intervals.vehicle,Math.max(0,intervals.page.offset-intervals.page.limit))}>Trước</button><button className="secondary" disabled={busy || intervals.page.offset+intervals.page.limit >= intervals.page.total} onClick={() => void traceVehicle(intervals.vehicle,intervals.page.offset+intervals.page.limit)}>Tiếp</button></article>}
    </section>}
  </main>;
}
