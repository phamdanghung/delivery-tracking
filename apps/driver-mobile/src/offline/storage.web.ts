// Web preview keeps credentials in memory; never persist tokens in browser storage.
import type { SqlStore } from "./outbox";
let session: string | null = null;
export const credentials = {
  get: async () => session,
  set: async (value: string) => { session = value; },
  remove: async () => { session = null; },
};
export const database: Promise<SqlStore> = Promise.resolve({
  execAsync: async () => {},
  runAsync: async (_sql, owner, name, value) => {
    localStorage.setItem(`fleet.driver.${owner}.${name}`, String(value));
  },
  getFirstAsync: async <T,>(_sql: string, owner: string | number, name: string | number) => {
    const value = localStorage.getItem(`fleet.driver.${owner}.${name}`);
    return value === null ? null : { value } as T;
  },
});
