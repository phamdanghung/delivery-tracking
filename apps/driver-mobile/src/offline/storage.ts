import * as SQLite from "expo-sqlite";
import * as SecureStore from "expo-secure-store";

export const database = SQLite.openDatabaseAsync("fleet-driver.db");
export const credentials = {
  get: () => SecureStore.getItemAsync("fleet.driver.session"),
  set: (value: string) => SecureStore.setItemAsync("fleet.driver.session", value),
  remove: () => SecureStore.deleteItemAsync("fleet.driver.session"),
};
