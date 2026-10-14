"use client";
import { useState } from "react";

type LinkCreated = { id: string; url: string; expires_at: string | null };
type Call = <T>(path: string, method?: string, data?: unknown) => Promise<T>;
export default function TrackingLinks({
  delivery,
  status,
  api,
}: {
  delivery: string;
  status: string;
  api: Call;
}) {
  const [links, setLinks] = useState<LinkCreated[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function create() {
    setBusy(true);
    setMessage("");
    try {
      const link = await api<LinkCreated>("tracking-links", "POST", {
        delivery_id: delivery,
      });
      setLinks((current) => [...current, link]);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Không tạo được link",
      );
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id: string) {
    setBusy(true);
    try {
      await api(`tracking-links/${id}/revoke`, "POST");
      setLinks((current) => current.filter((link) => link.id !== id));
      setMessage("Đã thu hồi link");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Không thu hồi được link",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card">
      <h2>Link theo dõi cho khách</h2>
      <p>
        Tạo và sao chép link để tự gửi qua Zalo. Link hết hạn 1 giờ sau khi giao
        xong.
      </p>
      <button
        disabled={
          busy || !["EN_ROUTE", "ARRIVED", "DELIVERING"].includes(status)
        }
        onClick={() => void create()}
      >
        Tạo link
      </button>
      {links.map((link) => (
        <div key={link.id}>
          <label>
            Link vừa tạo
            <input readOnly value={link.url} />
          </label>
          <button
            onClick={() =>
              void navigator.clipboard.writeText(link.url).then(
                () => setMessage("Đã sao chép"),
                () => setMessage("Hãy chọn và sao chép link"),
              )
            }
          >
            Sao chép
          </button>
          <button disabled={busy} onClick={() => void revoke(link.id)}>
            Thu hồi
          </button>
        </div>
      ))}
      <p>
        Link chỉ được trả khi tạo. Hãy lưu ID link nếu cần thu hồi sau khi rời
        trang.
      </p>
      {links.map((link) => (
        <p key={`id-${link.id}`}>ID link: {link.id}</p>
      ))}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const id = String(new FormData(event.currentTarget).get("id"));
          if (/^[0-9a-f-]{36}$/.test(id)) void revoke(id);
          else setMessage("ID link chưa hợp lệ");
        }}
      >
        <label>
          ID link cần thu hồi
          <input name="id" required />
        </label>
        <button disabled={busy}>Thu hồi theo ID</button>
      </form>
      <p role="status">{message}</p>
    </section>
  );
}
