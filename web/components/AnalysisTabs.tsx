"use client";

// The nine v1 result tabs, reproduced 1:1 against the API result shape.
// Chart presence is data-driven: the pipeline only emits a chart when its
// v1 guard passed, so each slot renders if the key exists.

import { useState } from "react";
import type { AnalysisResult } from "@/lib/types";
import PlotlyChart from "./PlotlyChart";
import StatTile from "./StatTile";

const TABS = [
  "Overview",
  "Morphology",
  "Street Network",
  "Transport",
  "Nature & Risk",
  "Cross-Analysis",
  "Stress & Risk",
  "Typology",
  "District Scores",
] as const;

function Charts({
  result,
  keys,
  cols = 2,
}: {
  result: AnalysisResult;
  keys: string[];
  cols?: 1 | 2 | 3;
}) {
  const present = keys.filter((k) => result.charts[k]);
  if (present.length === 0) return null;
  const grid =
    cols === 1 ? "grid-cols-1" : cols === 2 ? "md:grid-cols-2" : "md:grid-cols-3";
  return (
    <div className={`grid grid-cols-1 ${grid} gap-3`}>
      {present.map((k) => (
        <PlotlyChart key={k} name={k} spec={result.charts[k]} />
      ))}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="panel p-6 text-center text-sm text-ink-dim font-mono">{text}</div>
  );
}

export default function AnalysisTabs({ result }: { result: AnalysisResult }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const m = result.metrics_summary;
  const s = result.scalars;
  const has = (...keys: string[]) => keys.some((k) => result.charts[k]);

  return (
    <div className="space-y-3">
      {/* tab strip */}
      <div className="flex flex-wrap gap-1 border-b border-edge pb-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 text-sm rounded-t font-medium transition-colors ${
              tab === t
                ? "text-accent-transport border-b-2 border-accent-transport bg-accent-transport/5"
                : "text-ink-dim hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatTile label="Total Buildings" value={m.total_buildings.toLocaleString()} />
            <StatTile label="Total POIs" value={m.total_pois.toLocaleString()} accent="poi" />
            <StatTile
              label="Green Space"
              value={`${m.green_space_pct.toFixed(1)}%`}
              accent="nature"
            />
            <StatTile label="Dominant Morphotype" value={m.dominant_morphotype} />
          </div>
          <Charts result={result} keys={["poi_dominance_map"]} cols={1} />
          <Charts result={result} keys={["poi_distribution", "landuse_composition"]} />
          <Charts result={result} keys={["poi_density_contour", "nearest_services"]} cols={1} />
        </div>
      )}

      {tab === "Morphology" &&
        (has("far_heatmap", "morphotype_clusters", "density_gradient") ? (
          <div className="space-y-3">
            <Charts
              result={result}
              keys={["far_heatmap", "morphotype_clusters"]}
              cols={1}
            />
            <Charts
              result={result}
              keys={["density_gradient", "morphological_transition", "urban_quality"]}
              cols={1}
            />
          </div>
        ) : (
          <Empty text="Module disabled or no morphology data for this run." />
        ))}

      {tab === "Street Network" &&
        (has("street_orientation", "street_radar", "street_centrality") ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <StatTile
                label="Orientation Entropy"
                value={s.orientation_entropy.toFixed(3)}
                accent="transport"
              />
              <StatTile
                label="Dead-End Ratio"
                value={`${(s.dead_end_ratio * 100).toFixed(1)}%`}
                accent="transport"
              />
              <StatTile
                label="Block Size Median"
                value={`${Math.round(s.block_size_median).toLocaleString()} m²`}
                accent="transport"
              />
            </div>
            <Charts result={result} keys={["street_orientation", "street_radar"]} />
            <Charts result={result} keys={["street_centrality"]} cols={1} />
          </div>
        ) : (
          <Empty text="Module disabled — enable Morphology & Buildings." />
        ))}

      {tab === "Transport" &&
        (has("road_hierarchy", "transit_heatmap", "transport_map", "fifteen_min_map") ? (
          <div className="space-y-3">
            <div
              className={`grid gap-3 ${
                s.score_15min_mean != null ? "grid-cols-2 md:grid-cols-4" : "grid-cols-3"
              }`}
            >
              <StatTile
                label="Transit Stops"
                value={s.transit_stops_count.toLocaleString()}
                accent="transport"
              />
              <StatTile
                label="Cycling Infrastructure"
                value={`${s.cycling_km.toFixed(1)} km`}
                accent="transport"
              />
              <StatTile
                label="Dominant Road Type"
                value={s.dominant_road}
                accent="transport"
              />
              {s.score_15min_mean != null && (
                <StatTile
                  label="15-Min City Score"
                  value={`${s.score_15min_mean.toFixed(0)} / 100`}
                  accent="transport"
                />
              )}
            </div>
            <Charts result={result} keys={["road_hierarchy", "transit_heatmap"]} />
            <Charts result={result} keys={["transport_map", "fifteen_min_map"]} cols={1} />
          </div>
        ) : (
          <Empty text="Module disabled — enable in the control panel." />
        ))}

      {tab === "Nature & Risk" &&
        (has("nature_map", "flood_risk_map", "terrain_elevation", "heat_island_map") ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <StatTile
                label="Green Space Coverage"
                value={`${m.green_space_pct.toFixed(1)}%`}
                accent="nature"
              />
              <StatTile
                label="High Flood Risk Zones"
                value={`${s.high_flood_pct.toFixed(1)}%`}
                accent="risk"
              />
              <StatTile
                label="Water Bodies"
                value={s.water_bodies_count.toLocaleString()}
              />
            </div>
            <Charts result={result} keys={["nature_map", "flood_risk_map"]} />
            <Charts result={result} keys={["nature_radar", "city_15min"]} />
            {has("terrain_elevation") && (
              <h3 className="stat-label pt-2">Terrain Analysis</h3>
            )}
            <Charts result={result} keys={["terrain_elevation", "terrain_flood_risk"]} />
            <Charts result={result} keys={["terrain_cross"]} cols={1} />
            <Charts result={result} keys={["twi_distribution", "slope_elevation"]} />
            {has("heat_island_map") && (
              <h3 className="stat-label pt-2">Urban Heat Island</h3>
            )}
            <Charts result={result} keys={["heat_island_map"]} cols={1} />
          </div>
        ) : (
          <Empty text="Module disabled — enable in the control panel." />
        ))}

      {tab === "Cross-Analysis" &&
        (has("opportunity_surface", "cross_morph_transport") ? (
          <div className="space-y-3">
            <Charts result={result} keys={["opportunity_surface"]} cols={1} />
            <Charts
              result={result}
              keys={[
                "cross_morph_transport",
                "cross_nature_density",
                "cross_transport_nature",
              ]}
              cols={3}
            />
            <Charts result={result} keys={["landuse_crossref", "urban_quality"]} cols={1} />
          </div>
        ) : (
          <Empty text="Cross-analysis requires morphology + transport + nature layers with ≥10 hex cells." />
        ))}

      {tab === "Stress & Risk" &&
        (has("stress_map") ? (
          <div className="space-y-3">
            <Charts result={result} keys={["stress_map"]} cols={1} />
            <Charts result={result} keys={["stress_decomp", "vulnerability_map"]} />
            <Charts result={result} keys={["stress_pareto", "vuln_vs_stress"]} cols={1} />
          </div>
        ) : (
          <Empty text="Urban stress requires morphology + transport + nature layers." />
        ))}

      {tab === "Typology" &&
        (has("fabric_matrix", "fabric_map") ? (
          <div className="space-y-3">
            <Charts result={result} keys={["fabric_matrix", "fabric_map"]} />
            <Charts result={result} keys={["morphotype_radar", "segregation_map"]} cols={1} />
          </div>
        ) : (
          <Empty text="Typology requires morphology + land-use diversity layers (skipped for small cities)." />
        ))}

      {tab === "District Scores" &&
        (has("district_scorecard") ? (
          <div className="space-y-3">
            <Charts result={result} keys={["district_scorecard"]} cols={1} />
            {result.district_scores.length > 0 && (
              <div className="panel p-3 overflow-x-auto">
                <div className="stat-label mb-2">Raw scores</div>
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="text-ink-dim text-left">
                      {Object.keys(result.district_scores[0]).map((c) => (
                        <th key={c} className="pr-4 pb-1 whitespace-nowrap">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.district_scores.map((row, i) => (
                      <tr key={i} className="border-t border-edge">
                        {Object.values(row).map((v, j) => (
                          <td key={j} className="pr-4 py-1 whitespace-nowrap">
                            {typeof v === "number" ? v.toFixed(3) : String(v)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <Empty text="No district boundaries found for this city, or insufficient hex coverage per district." />
        ))}

      {/* AI insights */}
      {result.ai_insights && (
        <div className="panel p-4 mt-2">
          <div className="stat-label mb-2">AI Analysis</div>
          <div className="text-sm text-ink-dim whitespace-pre-line leading-relaxed">
            {result.ai_insights}
          </div>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="panel border-accent-risk/40 p-3 text-xs text-accent-risk font-mono space-y-1">
          {result.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  );
}
