"use client";

// Interactive draw tool for "Custom area" mode (UI addendum §2.3): the user
// draws a rectangle (or polygon) on a real map; we extract the geometry's
// bounds programmatically — raw coordinates are never typed or shown.
// Plain Leaflet + geoman (standard, well-documented) loaded client-side only.

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";

type Bbox = [number, number, number, number]; // min_lon, min_lat, max_lon, max_lat

export default function DrawMap({
  cityBbox,
  onBbox,
}: {
  cityBbox: Bbox | null;
  onBbox: (bbox: Bbox | null) => void;
}) {
  const divRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layerRef = useRef<any>(null);
  const onBboxRef = useRef(onBbox);
  onBboxRef.current = onBbox;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      await import("@geoman-io/leaflet-geoman-free");
      if (cancelled || !divRef.current || mapRef.current) return;

      const map = L.map(divRef.current, { attributionControl: false });
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        { maxZoom: 19 },
      ).addTo(map);
      map.setView([46.6, 2.4], 4);

      map.pm.addControls({
        position: "topleft",
        drawRectangle: true,
        drawPolygon: true,
        editMode: true,
        removalMode: true,
        drawMarker: false,
        drawCircle: false,
        drawCircleMarker: false,
        drawPolyline: false,
        drawText: false,
        dragMode: false,
        cutPolygon: false,
        rotateMode: false,
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const emit = (layer: any) => {
        const b = layer.getBounds();
        onBboxRef.current([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      map.on("pm:create", (e: any) => {
        if (layerRef.current) map.removeLayer(layerRef.current); // one zone at a time
        layerRef.current = e.layer;
        emit(e.layer);
        e.layer.on("pm:edit", () => layerRef.current && emit(layerRef.current));
      });
      map.on("pm:remove", () => {
        layerRef.current = null;
        onBboxRef.current(null);
      });

      mapRef.current = map;
      if (cityBbox) {
        map.fitBounds([
          [cityBbox[1], cityBbox[0]],
          [cityBbox[3], cityBbox[2]],
        ]);
      }
    })();
    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        layerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-center when the city bbox arrives after mount
  useEffect(() => {
    if (mapRef.current && cityBbox) {
      mapRef.current.fitBounds([
        [cityBbox[1], cityBbox[0]],
        [cityBbox[3], cityBbox[2]],
      ]);
    }
  }, [cityBbox]);

  return (
    <div>
      <div
        ref={divRef}
        className="h-72 rounded overflow-hidden border border-edge"
      />
      <p className="text-[10px] text-ink-faint mt-1">
        Draw a rectangle (or polygon) over the area to analyze. Redrawing
        replaces the previous zone.
      </p>
    </div>
  );
}
