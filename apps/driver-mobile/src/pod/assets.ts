import { Directory, File, Paths } from "expo-file-system";
import { CryptoDigestAlgorithm, digest } from "expo-crypto";

function location(owner: string, id: string) {
  if (![owner, id].every((value) => /^[0-9a-f-]{36}$/i.test(value))) throw new Error("Mã ảnh không hợp lệ");
  const directory = new Directory(Paths.document, "pod", owner);
  directory.create({ intermediates: true, idempotent: true });
  return new File(directory, id);
}
export async function hash(bytes: Uint8Array<ArrayBuffer>) {
  return Array.from(new Uint8Array(await digest(CryptoDigestAlgorithm.SHA256, bytes))).map((x) => x.toString(16).padStart(2, "0")).join("");
}
export async function saveAsset(owner: string, id: string, uri: string) {
  const source = new File(uri); const target = location(owner, id);
  if (!source.size || source.size > 20 * 1024 * 1024) throw new Error("Ảnh trống hoặc vượt 20 MB");
  const sha256 = await hash(await source.bytes());
  if (target.exists) {
    if (await hash(await target.bytes()) !== sha256) throw new Error("Mã ảnh đã dùng cho nội dung khác");
  } else { source.copy(target); }
  if (await hash(await target.bytes()) !== sha256) throw new Error("Không lưu được ảnh nguyên vẹn; hãy thử lại");
  return { sha256, size_bytes: target.size };
}
export async function readAsset(owner: string, id: string, sha256: string) {
  const file = location(owner, id);
  if (!file.exists) throw new Error("Không tìm thấy ảnh đã lưu; giữ thao tác để kiểm tra");
  const bytes = await file.bytes();
  if (await hash(bytes) !== sha256) throw new Error("Ảnh đã lưu không khớp hash; không upload");
  return bytes;
}
export async function previewAsset(owner: string, id: string) { return location(owner, id).uri; }
