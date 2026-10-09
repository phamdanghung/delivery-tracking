"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { showTime, statusLabels } from "../dispatch/helpers";

const Map = dynamic(() => import("../fleet/map"), { ssr: false });
type Tracking = {
  code: string;
  status: string;
  completed_at: string | null;
  expires_at: string | null;
  gps: {
    latitude: number;
    longitude: number;
    updated_at: string;
    freshness: string;
  } | null;
  eta_at: string | null;
  eta_status: string;
};
export default function CustomerTracking({ token }: { token: string }) {
  const [value, setValue] = useState<Tracking | null>(null);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    let stopped = false;
    const controller = new AbortController();
    const load = async () => {
      if (stopped) return;
      try {
        const response = await fetch(
          `/api/public/tracking/${encodeURIComponent(token)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!active) return;
        if (response.status === 410) {
          stopped = true;
          setValue(null);
          setExpired(true);
          setError(false);
          return;
        }
        if (!response.ok) throw new Error("Unavailable");
        const data = (await response.json()) as Tracking;
        if (!active) return;
        setValue(data);
        setError(false);
      } catch {
        if (active) {
          setError(true);
          setValue(null);
        }
      }
    };
    void load();
    const timer = setInterval(() => void load(), 10000);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, [token, retry]);
  useEffect(() => {
    if (!value?.expires_at) return;
    const timer = setTimeout(
      () => {
        setValue(null);
        setExpired(true);
      },
      Math.max(0, Date.parse(value.expires_at) - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [value?.expires_at]);
  return (
    <main className="customer-tracking">
      <h1>Theo dõi giao hàng</h1>
      <div aria-live="polite">
        {expired ? (
          <section className="card">
            <h2>Liên kết không còn hiệu lực</h2>
            <p>Vui lòng liên hệ người gửi để được hỗ trợ.</p>
          </section>
        ) : error ? (
          <section className="card">
            <p>Chưa thể tải dữ liệu giao hàng.</p>
            <button onClick={() => setRetry((x) => x + 1)}>Thử lại</button>
          </section>
        ) : !value ? (
          <p>Đang tải thông tin giao hàng…</p>
        ) : (
          <>
            <section className="card">
              <p>Đơn {value.code}</p>
              <h2>{statusLabels[value.status] || value.status}</h2>
              {value.status === "DELIVERED" ? (
                <p>Đã giao lúc {showTime(value.completed_at)}</p>
              ) : (
                <>
                  <h2>
                    {value.eta_at
                      ? `Dự kiến đến ${showTime(value.eta_at)}`
                      : "ETA chưa xác định"}
                  </h2>
                  <p>
                    Thời gian dự kiến được cập nhật theo hành trình thực tế.
                  </p>
                </>
              )}
            </section>
            {value.status !== "DELIVERED" && (
              <section className="card">
                <h2>Vị trí xe giao hàng</h2>
                {value.gps ? (
                  <>
                    <p>
                      {value.gps.freshness === "NORMAL"
                        ? "Vị trí GPS thực tế"
                        : "Vị trí ghi nhận gần nhất; GPS chưa cập nhật"}{" "}
                      · {showTime(value.gps.updated_at)}
                    </p>
                    <Map
                      points={[
                        {
                          ...value.gps,
                          label: "Xe đang giao đơn của bạn",
                          stale: value.gps.freshness !== "NORMAL",
                        },
                      ]}
                    />
                  </>
                ) : (
                  <p>Chưa có vị trí GPS hợp lệ.</p>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
