export type Freshness = "NORMAL" | "STALE" | "LOST";
export type Position = {
  latitude: number | null;
  longitude: number | null;
  speed_kmh: number | null;
  course: number | null;
  gps_at: string | null;
  server_received_at: string | null;
  acc: boolean | null;
  engine_state: "MOVING" | "IDLING" | "PARKED" | "UNKNOWN";
  valid: boolean;
};
export function gpsFreshness(
  position: Position | null,
  now = Date.now(),
): Freshness {
  if (!position?.valid || !position.gps_at || !position.server_received_at)
    return "LOST";
  const fix = Date.parse(position.gps_at),
    received = Date.parse(position.server_received_at);
  if (
    !Number.isFinite(fix) ||
    !Number.isFinite(received) ||
    fix > now ||
    received > now
  )
    return "LOST";
  const age = Math.max(now - fix, now - received);
  return age <= 30000 ? "NORMAL" : age <= 120000 ? "STALE" : "LOST";
}
export const gpsLabels = {
  NORMAL: "Bình thường",
  STALE: "Dữ liệu chậm",
  LOST: "Mất tín hiệu GPS",
};
export const engineLabels = {
  MOVING: "Đang chạy",
  IDLING: "Dừng nổ máy",
  PARKED: "Tắt máy / đỗ",
  UNKNOWN: "Không xác định",
};
