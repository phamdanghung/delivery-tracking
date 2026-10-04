"use client";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";

type MapPoint = {
  latitude: number;
  longitude: number;
  label: string;
  stale?: boolean;
  selected?: boolean;
};
export default function FleetMap({
  points,
  segments = [],
}: {
  points: MapPoint[];
  segments?: MapPoint[][];
}) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const layer = useRef<LayerGroup | null>(null);
  const framed = useRef<string | null>(null);
  const [ready, setReady] = useState(false);
  const [tileError, setTileError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || !element.current) return;
      map.current = L.map(element.current).setView([10.7769, 106.7009], 12);
      const tiles = L.tileLayer(
        process.env.NEXT_PUBLIC_MAP_TILE_URL ||
          "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        },
      ).addTo(map.current);
      tiles.on("tileerror", () => setTileError(true));
      layer.current = L.layerGroup().addTo(map.current);
      setReady(true);
    });
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || !map.current || !layer.current) return;
      layer.current.clearLayers();
      for (const point of points) {
        const label = document.createElement("span");
        label.textContent = point.label;
        L.circleMarker([point.latitude, point.longitude], {
          radius: point.selected ? 12 : 8,
          weight: point.selected ? 4 : 2,
          color: point.stale ? "#B45309" : "#0F6CBD",
          fillOpacity: point.stale ? 0.35 : 0.85,
          dashArray: point.stale ? "4 4" : undefined,
        })
          .bindTooltip(label, { permanent: point.selected })
          .addTo(layer.current);
      }
      for (const segment of segments) {
        L.polyline(
          segment.map((p) => [p.latitude, p.longitude] as [number, number]),
          { color: "#0F6CBD" },
        ).addTo(layer.current);
      }
      const coordinates = [...points, ...segments.flat()].map((p) =>
        L.latLng(p.latitude, p.longitude),
      );
      const selection = points
        .filter((p) => p.selected)
        .map((p) => p.label.split(" · ")[0])
        .join("|");
      if (coordinates.length && framed.current !== selection) {
        map.current.fitBounds(L.latLngBounds(coordinates), {
          padding: [32, 32],
          maxZoom: 15,
        });
        framed.current = selection;
      }
    });
    return () => {
      cancelled = true;
    };
  }, [points, segments, ready]);
  return (
    <div className="map-frame">
      {!ready && <p role="status">Đang tải bản đồ…</p>}
      {tileError && (
        <p className="map-warning" role="alert">
          Không tải được nền bản đồ. Tọa độ và trạng thái xe vẫn được hiển thị.
        </p>
      )}
      <div ref={element} className="fleet-map" aria-label="Bản đồ vị trí xe" />
    </div>
  );
}
