import { CryptoDigestAlgorithm, digest } from "expo-crypto";

async function open() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("fleet-pod", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("photos");
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  });
}
async function stored(owner: string, id: string) {
  const database = await open();
  try { return await new Promise<Blob | undefined>((resolve, reject) => {
    const request = database.transaction("photos").objectStore("photos").get(`${owner}/${id}`);
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  }); } finally { database.close(); }
}
export async function hash(bytes: Uint8Array<ArrayBuffer>) {
  return Array.from(new Uint8Array(await digest(CryptoDigestAlgorithm.SHA256, bytes))).map((x) => x.toString(16).padStart(2, "0")).join("");
}
export async function saveAsset(owner: string, id: string, uri: string) {
  const blob = await (await fetch(uri)).blob();
  if (!blob.size || blob.size > 20 * 1024 * 1024) throw new Error("Ảnh trống hoặc vượt 20 MB");
  const sha256 = await hash(new Uint8Array(await blob.arrayBuffer()));
  const database = await open();
  let existing: Blob | undefined;
  try { await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction("photos", "readwrite");
    const store = transaction.objectStore("photos");
    const request = store.get(`${owner}/${id}`);
    request.onsuccess = () => { existing = request.result; if (!existing) store.add(blob, `${owner}/${id}`); };
    transaction.oncomplete = () => resolve(); transaction.onabort = () => reject(new Error("Mã ảnh đã tồn tại; không ghi đè"));
    transaction.onerror = () => reject(transaction.error);
  }); } finally { database.close(); }
  if (existing && await hash(new Uint8Array(await existing.arrayBuffer())) !== sha256) throw new Error("Mã ảnh đã dùng cho nội dung khác; không ghi đè");
  return { sha256, size_bytes: blob.size };
}
export async function readAsset(owner: string, id: string, sha256: string) {
  const blob = await stored(owner, id);
  if (!blob) throw new Error("Không tìm thấy ảnh đã lưu; giữ thao tác để kiểm tra");
  const bytes = new Uint8Array(await blob.arrayBuffer());
  if (await hash(bytes) !== sha256) throw new Error("Ảnh đã lưu không khớp hash; không upload");
  return bytes;
}
export async function previewAsset(owner: string, id: string) {
  const blob = await stored(owner, id); return blob ? URL.createObjectURL(blob) : "";
}
