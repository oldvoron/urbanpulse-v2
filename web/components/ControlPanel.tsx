"use client";

// v1 sidebar reproduced, with the Variant C zone system (UI addendum §2):
// Entire city | District (live OSM-sourced dropdown) | Custom area (map draw).

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  AnalyzeConfig,
  CITY_SIZES,
  DistrictsResponse,
  MODULE_TOGGLES,
  ZONE_MODES,
} from "@/lib/types";
import { getDistricts } from "@/lib/api";

const DrawMap = dynamic(() => import("./DrawMap"), {
  ssr: false,
  loading: () => (
    <div className="h-72 rounded border border-edge flex items-center justify-center text-ink-faint text-xs font-mono">
      loading map…
    </div>
  ),
});

export interface ControlState {
  cityName: string;
  citySize: string;
  zoneMode: string; // API value: "Entire city" | "Select district" | "Draw custom bbox"
  selectedDistrict: string;
  customBbox: [number, number, number, number] | null;
  modules: Record<string, boolean>;
}

export function defaultControls(): ControlState {
  return {
    cityName: "",
    citySize: CITY_SIZES[1],
    zoneMode: "Entire city",
    selectedDistrict: "All",
    customBbox: null,
    modules: Object.fromEntries(MODULE_TOGGLES.map((t) => [t.key, true])),
  };
}

export function controlsToConfig(c: ControlState): AnalyzeConfig {
  return {
    city_size: c.citySize,
    zone_mode: c.zoneMode,
    selected_district:
      c.zoneMode === "Select district" ? c.selectedDistrict : undefined,
    custom_bbox:
      c.zoneMode === "Draw custom bbox" && c.customBbox
        ? c.customBbox
        : undefined,
    ...c.modules,
  };
}

type DistrictsState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; data: DistrictsResponse }
  | { kind: "error"; message: string };

export default function ControlPanel({
  state,
  onChange,
  onAnalyze,
  busy,
}: {
  state: ControlState;
  onChange: (s: ControlState) => void;
  onAnalyze: () => void;
  busy: boolean;
}) {
  const [showModules, setShowModules] = useState(false);
  const [districts, setDistricts] = useState<DistrictsState>({ kind: "idle" });
  const stateRef = useRef(state);
  stateRef.current = state;
  const set = (patch: Partial<ControlState>) => onChange({ ...stateRef.current, ...patch });

  // Fetch the district list (and city bbox for the draw map) whenever a zone
  // mode that needs it is active and a city name is present. Debounced;
  // server caches per city, so repeats are cheap.
  const needsCityMeta =
    state.zoneMode === "Select district" || state.zoneMode === "Draw custom bbox";
  const city = state.cityName.trim();
  useEffect(() => {
    if (!needsCityMeta || !city) {
      setDistricts({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setDistricts({ kind: "loading" });
    const t = setTimeout(() => {
      getDistricts(city)
        .then((data) => {
          if (cancelled) return;
          setDistricts({ kind: "loaded", data });
        })
        .catch((e) => {
          if (!cancelled)
            setDistricts({
              kind: "error",
              message: e instanceof Error ? e.message : String(e),
            });
        });
    }, 700);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [needsCityMeta, city]);

  const loadedDistricts =
    districts.kind === "loaded" ? districts.data.districts : [];
  const cityBbox =
    districts.kind === "loaded" ? districts.data.city_bbox : null;

  return (
    <aside className="panel p-4 space-y-4 h-fit lg:sticky lg:top-16">
      <div className="stat-label">Settings</div>

      <label className="block space-y-1">
        <span className="text-xs text-ink-dim">City size</span>
        <select
          className="input-dark"
          value={state.citySize}
          onChange={(e) => set({ citySize: e.target.value })}
        >
          {CITY_SIZES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>

      <label className="block space-y-1">
        <span className="text-xs text-ink-dim">City name</span>
        <input
          className="input-dark"
          placeholder="e.g. Blois, France"
          value={state.cityName}
          onChange={(e) => set({ cityName: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !busy && state.cityName.trim()) onAnalyze();
          }}
        />
      </label>

      <button
        className="btn-primary w-full"
        disabled={busy || !state.cityName.trim()}
        onClick={onAnalyze}
      >
        {busy ? "Analyzing…" : "Analyze"}
      </button>

      <div className="border-t border-edge pt-3 space-y-2">
        <div className="stat-label">Analysis Zone</div>
        {ZONE_MODES.map((z) => (
          <label key={z.value} className="flex items-center gap-2 text-sm text-ink-dim">
            <input
              type="radio"
              checked={state.zoneMode === z.value}
              onChange={() => set({ zoneMode: z.value })}
              className="accent-[#2DD4EF]"
            />
            {z.label}
          </label>
        ))}

        {/* District mode: live OSM-sourced dropdown (§2.2) */}
        {state.zoneMode === "Select district" && (
          <div className="pt-1 space-y-2">
            {!city && (
              <p className="text-[11px] text-ink-faint">
                Enter a city name above to load its districts.
              </p>
            )}
            {city && districts.kind === "loading" && (
              <p className="text-[11px] text-ink-faint font-mono">
                Loading district list from OSM…
              </p>
            )}
            {city && districts.kind === "error" && (
              <p className="text-[11px] text-accent-risk font-mono">
                {districts.message}
              </p>
            )}
            {districts.kind === "loaded" &&
              (loadedDistricts.length > 0 ? (
                <label className="block space-y-1">
                  <span className="text-[11px] text-ink-faint">
                    {loadedDistricts.length} subdivisions (OSM admin level{" "}
                    {districts.data.level_used})
                  </span>
                  <select
                    className="input-dark"
                    value={state.selectedDistrict}
                    onChange={(e) => set({ selectedDistrict: e.target.value })}
                  >
                    <option value="All">All (entire city)</option>
                    {loadedDistricts.map((d) => (
                      <option key={d.osm_id || d.name} value={d.name}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="text-[11px] text-ink-dim space-y-2">
                  <p>
                    No sub-city districts found in OSM for this city — try
                    drawing a custom area instead.
                  </p>
                  <button
                    className="btn-ghost !text-xs"
                    onClick={() => set({ zoneMode: "Draw custom bbox" })}
                  >
                    Switch to Custom area →
                  </button>
                </div>
              ))}
          </div>
        )}

        {/* Custom area mode: interactive map draw (§2.3) */}
        {state.zoneMode === "Draw custom bbox" && (
          <div className="pt-1 space-y-1">
            <DrawMap
              cityBbox={cityBbox}
              onBbox={(bbox) => set({ customBbox: bbox })}
            />
            {state.customBbox ? (
              <p className="text-[10px] font-mono text-accent-transport">
                ✓ Zone selected
              </p>
            ) : (
              <p className="text-[10px] text-ink-faint">
                No zone drawn yet — analysis will use the entire city.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-edge pt-3">
        <button
          className="stat-label w-full text-left hover:text-ink"
          onClick={() => setShowModules(!showModules)}
        >
          Analysis Modules {showModules ? "▾" : "▸"}
        </button>
        {showModules && (
          <div className="pt-2 space-y-1.5">
            {MODULE_TOGGLES.map((t) => (
              <label key={t.key} className="flex items-center gap-2 text-sm text-ink-dim">
                <input
                  type="checkbox"
                  checked={state.modules[t.key]}
                  onChange={(e) =>
                    set({ modules: { ...state.modules, [t.key]: e.target.checked } })
                  }
                  className="accent-[#2DD4EF]"
                />
                {t.label}
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-edge pt-3 text-[10px] text-ink-faint font-mono space-y-0.5">
        <div>Data: Overture Maps + OpenStreetMap</div>
        <div>AI: Claude</div>
      </div>
    </aside>
  );
}
