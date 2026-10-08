/** Persist before displaying success; replay the exact immutable command after timeout/restart. */
export type Command = {
  client_action_id: string;
  occurred_at: string;
  action: { kind: "START_TRIP" | "STATUS" | "PROPOSE_RESCHEDULE" | "CORRECT_ARRIVED"; resource_id: string; data?: unknown };
  replaces_client_action_id?: string;
};
export type Review = { review_token: string; state: Record<string, unknown>; conflict: string };
export type Resolution = { review_token: string; reason: string; decided_at: string };
export type PendingAction = {
  command: Command; state: "WAITING" | "SYNCING" | "SYNCED" | "ERROR" | "CONFLICT" | "DISCARDED";
  error?: string; entity_keys?: string[]; review?: Review; resolution?: Resolution;
  resolution_attempts?: Resolution[]; replacement_id?: string;
};
export const finished = (item: PendingAction) => item.state === "SYNCED" || item.state === "DISCARDED";
export const entityKeys = (command: Command, trips: { id: string; stops: { delivery_id: string }[] }[] = []) => command.action.kind === "START_TRIP"
  ? [`trip:${command.action.resource_id}`, ...(trips.find((x) => x.id === command.action.resource_id)?.stops.map((x) => `delivery:${x.delivery_id}`) ?? [])]
  : [`delivery:${command.action.resource_id}`];
export function eligible(items: PendingAction[]): PendingAction | undefined {
  const blocked = new Set<string>();
  for (const item of items) {
    if (finished(item)) continue;
    if (item.state === "ERROR") return; // Preserve non-conflict error handling.
    const keys = item.entity_keys ?? entityKeys(item.command);
    if (item.state === "CONFLICT") { keys.forEach((key) => blocked.add(key)); continue; }
    if (keys.some((key) => blocked.has(key))) { keys.forEach((key) => blocked.add(key)); continue; }
    return item;
  }
}
export interface SqlStore {
  execAsync(sql: string): Promise<void>;
  runAsync(sql: string, ...values: (string | number)[]): Promise<unknown>;
  getFirstAsync<T>(sql: string, ...values: (string | number)[]): Promise<T | null>;
}
export class Outbox {
  private tail: Promise<unknown> = Promise.resolve();
  private syncing: Promise<void> | null = null;
  constructor(private db: SqlStore, readonly owner: string) {}
  async init() {
    await this.db.execAsync("CREATE TABLE IF NOT EXISTS driver_local (owner TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(owner,name))");
    const cache = await this.load<{ trips: { id: string; stops: { delivery_id: string }[] }[] }>("today");
    await this.update((items) => items.map((x) => ({ ...x, entity_keys: x.entity_keys ?? entityKeys(x.command, cache?.trips), state: x.state === "SYNCING" ? "WAITING" : x.state })));
  }
  async load<T>(name: string): Promise<T | null> {
    const row = await this.db.getFirstAsync<{ value: string }>("SELECT value FROM driver_local WHERE owner=? AND name=?", this.owner, name);
    return row ? JSON.parse(row.value) : null;
  }
  async save(name: string, value: unknown) {
    await this.db.runAsync("INSERT INTO driver_local(owner,name,value) VALUES(?,?,?) ON CONFLICT(owner,name) DO UPDATE SET value=excluded.value", this.owner, name, JSON.stringify(value));
  }
  async list(): Promise<PendingAction[]> { return await this.load<PendingAction[]>("outbox") ?? []; }
  private update(change: (items: PendingAction[]) => PendingAction[]) {
    const operation = this.tail.then(async () => { await this.save("outbox", change(await this.list())); });
    this.tail = operation.catch(() => {});
    return operation;
  }
  async enqueue(command: Command, keys = entityKeys(command)) {
    await this.update((items) => {
      const old = items.find((x) => x.command.client_action_id === command.client_action_id);
      if (old && JSON.stringify(old.command) !== JSON.stringify(command)) throw new Error("Mã thao tác đã được dùng");
      if (old) return items;
      const previous = [...items].reverse().find((x) => x.state === "DISCARDED" && !x.replacement_id && x.command.action.resource_id === command.action.resource_id && (x.command.action.kind === "START_TRIP") === (command.action.kind === "START_TRIP"));
      const linked = previous ? { ...command, replaces_client_action_id: previous.command.client_action_id } : command;
      return [...items.map((x) => x === previous ? { ...x, replacement_id: linked.client_action_id } : x), { command: linked, entity_keys: keys, state: "WAITING" }];
    });
  }
  async reviewed(id: string, review: Review) {
    await this.update((items) => items.map((x) => x.command.client_action_id === id && x.state === "CONFLICT" && !x.resolution ? { ...x, review } : x));
  }
  async discard(id: string, reason: string, decidedAt: string) {
    await this.update((items) => items.map((x) => {
      if (x.command.client_action_id !== id) return x;
      if (x.state !== "CONFLICT" || !x.review || x.resolution || !reason.trim()) throw new Error("Xem dữ liệu mới và nhập lý do trước khi xác nhận bỏ");
      const resolution = { review_token: x.review.review_token, reason: reason.trim(), decided_at: decidedAt };
      return { ...x, resolution, resolution_attempts: [...(x.resolution_attempts ?? []), resolution] };
    }));
  }
  async retry() {
    await this.update((items) => items.map((x) => x.state === "ERROR" ? { ...x, state: "WAITING", error: undefined } : x));
  }
  async sync(send: (command: Command) => Promise<{ ok: boolean; retryable: boolean; conflict?: boolean; error?: string }>, changed: () => void,
    resolve?: (command: Command, resolution: Resolution) => Promise<{ ok: boolean; retryable: boolean; error?: string }>) {
    if (this.syncing) return this.syncing;
    this.syncing = (async () => {
      for (;;) {
        const items = await this.list();
        const decision = resolve && items.find((x) => x.state === "CONFLICT" && x.resolution);
        if (decision && resolve) {
          let result;
          try { result = await resolve(decision.command, decision.resolution!); }
          catch { result = { ok: false, retryable: true, error: "Chưa gửi được quyết định bỏ; giữ nguyên trên máy" }; }
          await this.update((all) => all.map((x) => x.command.client_action_id === decision.command.client_action_id ? {
            ...x, state: result.ok ? "DISCARDED" : "CONFLICT", error: result.error,
            resolution: result.ok || result.retryable ? x.resolution : undefined,
            review: result.ok || result.retryable ? x.review : undefined,
          } : x));
          changed();
          if (!result.ok && result.retryable) break;
          continue;
        }
        const next = eligible(items);
        if (!next) break;
        const id = next.command.client_action_id;
        await this.update((all) => all.map((x) => x.command.client_action_id === id ? { ...x, state: "SYNCING" } : x));
        changed();
        let result;
        try { result = await send(next.command); }
        catch { result = { ok: false, retryable: true, error: "Mất kết nối — thao tác vẫn được lưu trên máy" }; }
        await this.update((all) => all.map((x) => x.command.client_action_id === id ? {
          ...x, state: result.ok ? "SYNCED" : result.conflict ? "CONFLICT" : result.retryable ? "WAITING" : "ERROR", error: result.error,
        } : x));
        changed();
        if (!result.ok && !result.conflict) break;
      }
    })().finally(() => { this.syncing = null; });
    return this.syncing;
  }
}
