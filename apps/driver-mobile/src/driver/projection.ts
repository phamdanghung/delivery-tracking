import type { Cache } from "./context";
import type { PendingAction } from "../offline/outbox";

export function projected(cache: Cache | null, queue: PendingAction[]): Cache | null {
  if (!cache) return null;
  const result = JSON.parse(JSON.stringify(cache)) as Cache;
  for (const item of queue) {
    if (item.state === "SYNCED") continue;
    if (item.state === "ERROR") break;
    const action = item.command.action;
    if (action.kind === "START_TRIP") {
      const trip = result.trips.find((x) => x.id === action.resource_id);
      if (trip?.status === "PLANNED") { trip.status = "ACTIVE"; for (const stop of trip.stops) { stop.status = "EN_ROUTE"; const d = result.deliveries[stop.delivery_id]?.delivery; if (d?.status === "ASSIGNED") d.status = "EN_ROUTE"; } }
    } else {
      const d = result.deliveries[action.resource_id]?.delivery;
      const data = action.data as { from_status?: string; to_status?: string };
      if (d && action.kind === "STATUS" && d.status === data.from_status && data.to_status) d.status = data.to_status;
      if (d && action.kind === "CORRECT_ARRIVED" && d.status === "ARRIVED") d.status = "EN_ROUTE";
    }
  }
  return result;
}
