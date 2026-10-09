"use client";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { showTime } from "./helpers";

type Photo = { id: string; trip_stop_id: string | null; source: string | null; captured_at: string; uploaded_at: string | null; latitude: number | null; longitude: number | null; gps_fix_at: string | null; gps_freshness: string | null; location_status: string | null; location_reason: string | null; created_by: string | null };
type Call = <T>(path: string, method?: string, data?: unknown) => Promise<T>;
export default function PodGallery({ delivery, api }: { delivery: string; api: Call }) {
  const [photos, setPhotos] = useState<Photo[]>([]); const [urls, setUrls] = useState<Record<string, string>>({});
  const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const items = await api<Photo[]>(`deliveries/${delivery}/pod/photos`);
      setPhotos(items);
      const links = await Promise.all(items.map(async (item) => {
        const response = await api<{ url: string }>(`deliveries/${delivery}/pod/photos/${item.id}/url`);
        return [item.id, response.url] as const;
      }));
      setUrls(Object.fromEntries(links));
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Không đọc được ảnh POD"); }
    finally { setLoading(false); }
  }, [api, delivery]);
  useEffect(() => { const timer = setTimeout(() => { void load(); }, 0); return () => clearTimeout(timer); }, [load]);
  return <section className="panel"><h2>Ảnh bằng chứng giao hàng</h2>
    <button disabled={loading} onClick={() => { void load(); }}>Tải lại ảnh / cấp lại quyền đọc</button>
    {loading && <p role="status">Đang tải ảnh…</p>}{!!error && <p role="alert">{error}</p>}
    {!loading && !error && !photos.length && <p>Chưa có ảnh POD.</p>}
    {photos.map((item) => <article key={item.id}>
      {urls[item.id] && <Image src={urls[item.id]} alt="Ảnh bằng chứng giao hàng" width={320} height={240} unoptimized style={{ objectFit: "contain" }} onError={() => setError("Quyền đọc ảnh có thể đã hết hạn; chọn tải lại ảnh.")}/>}
      <p>{item.source === "CAMERA_CAPTURED" ? "Camera" : item.source === "ALBUM_SELECTED" ? "Album" : "Ảnh lịch sử"} · {showTime(item.captured_at)} · Upload {showTime(item.uploaded_at)}</p>
      <p>Lượt giao: {item.trip_stop_id ?? "Chưa có metadata lượt giao"} · Người tạo: {item.created_by ?? "Chưa xác minh"}</p>
      <p>{item.location_status === "VERIFIED" ? `GPS ${item.latitude}, ${item.longitude} · ${showTime(item.gps_fix_at)} · ${item.gps_freshness}` : `Vị trí chưa xác minh: ${item.location_reason ?? "Metadata lịch sử"}`}</p>
    </article>)}
  </section>;
}
