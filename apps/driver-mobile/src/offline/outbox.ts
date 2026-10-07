/** Persist before displaying success; replay the exact immutable command after timeout/restart. */
export type Command = {
  client_action_id: string;
  occurred_at: string;
  action: { kind: "START_TRIP" | "STATUS" | "PROPOSE_RESCHEDULE" | "CORRECT_ARRIVED"; resource_id: string; data?: unknown };
};
export type PendingAction = { command: Command; state: "WAITING" | "SYNCING" | "SYNCED" | "ERROR"; error?: string };
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
    await this.update((items) => items.map((x) => x.state === "SYNCING" ? { ...x, state: "WAITING" } : x));
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
  async enqueue(command: Command) {
    await this.update((items) => {
      const old = items.find((x) => x.command.client_action_id === command.client_action_id);
      if (old && JSON.stringify(old.command) !== JSON.stringify(command)) throw new Error("Mã thao tác đã được dùng");
      return old ? items : [...items, { command, state: "WAITING" }];
    });
  }
  async retry() {
    await this.update((items) => items.map((x) => x.state === "ERROR" ? { ...x, state: "WAITING", error: undefined } : x));
  }
  async sync(send: (command: Command) => Promise<{ ok: boolean; retryable: boolean; error?: string }>, changed: () => void) {
    if (this.syncing) return this.syncing;
    this.syncing = (async () => {
      for (;;) {
        const items = await this.list();
        // A rejected predecessor blocks dependent commands. Never skip ahead or drop user data.
        const next = items.find((x) => x.state !== "SYNCED");
        if (!next || next.state === "ERROR") break;
        const id = next.command.client_action_id;
        await this.update((all) => all.map((x) => x.command.client_action_id === id ? { ...x, state: "SYNCING" } : x));
        changed();
        let result;
        try { result = await send(next.command); }
        catch { result = { ok: false, retryable: true, error: "Mất kết nối — thao tác vẫn được lưu trên máy" }; }
        await this.update((all) => all.map((x) => x.command.client_action_id === id ? {
          ...x, state: result.ok ? "SYNCED" : result.retryable ? "WAITING" : "ERROR", error: result.error,
        } : x));
        changed();
        if (!result.ok) break;
      }
    })().finally(() => { this.syncing = null; });
    return this.syncing;
  }
}
