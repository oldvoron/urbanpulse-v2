"use client";

// v1 sidebar reproduced: city size, city name, zone mode, module toggles.

import { useState } from "react";
import {
  AnalyzeConfig,
  CITY_SIZES,
  MODULE_TOGGLES,
  ZONE_MODES,
} from "@/lib/types";

export interface ControlState {
  cityName: string;
  citySize: string;
  zoneMode: string;
  customBbox: [number, number, number, number];
  modules: Record<string, boolean>;
}

export function defaultControls(): ControlState {
  return {
    cityName: "",
    citySize: CITY_SIZES[1],
    zoneMode: ZONE_MODES[0],
    customBbox: [0, 0, 0, 0],
    modules: Object.fromEntries(MODULE_TOGGLES.map((t) => [t.key, true])),
  };
}

export function controlsToConfig(c: ControlState): AnalyzeConfig {
  return {
    city_size: c.citySize,
    zone_mode: c.zoneMode,
    custom_bbox: c.zoneMode === "Draw custom bbox" ? c.customBbox : undefined,
    ...c.modules,
  };
}

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
  const set = (patch: Partial<ControlState>) => onChange({ ...state, ...patch });

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
        {ZONE_MODES.filter((z) => z !== "Select district").map((z) => (
          <label key={z} className="flex items-center gap-2 text-sm text-ink-dim">
            <input
              type="radio"
              checked={state.zoneMode === z}
              onChange={() => set({ zoneMode: z })}
              className="accent-[#2DD4EF]"
            />
            {z}
          </label>
        ))}
        {state.zoneMode === "Draw custom bbox" && (
          <div className="grid grid-cols-2 gap-2 pt-1">
            {(["Min lat", "Min lon", "Max lat", "Max lon"] as const).map(
              (label, i) => {
                // custom_bbox order is (min_lon, min_lat, max_lon, max_lat)
                const idx = [1, 0, 3, 2][i];
                return (
                  <label key={label} className="space-y-0.5">
                    <span className="text-[10px] text-ink-faint">{label}</span>
                    <input
                      className="input-dark font-mono !py-1"
                      type="number"
                      step="0.0001"
                      value={state.customBbox[idx]}
                      onChange={(e) => {
                        const bbox = [...state.customBbox] as ControlState["customBbox"];
                        bbox[idx] = parseFloat(e.target.value) || 0;
                        set({ customBbox: bbox });
                      }}
                    />
                  </label>
                );
              },
            )}
            <p className="col-span-2 text-[10px] text-ink-faint">
              Tip: copy bbox coords from the city overview map
            </p>
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
