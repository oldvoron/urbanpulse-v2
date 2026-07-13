// Shapes returned by the Urban Pulse API (api/main.py + engine/pipeline.py).

export interface MetricsSummary {
  total_buildings: number;
  total_pois: number;
  median_height: number;
  green_space_pct: number;
  transport_index_mean: number;
  urban_stress_mean: number;
  dominant_morphotype: string;
}

export interface Scalars {
  orientation_entropy: number;
  dead_end_ratio: number;
  block_size_median: number;
  transit_stops_count: number;
  cycling_km: number;
  dominant_road: string;
  water_bodies_count: number;
  high_flood_pct: number;
  city_center_lat: number;
  city_center_lon: number;
  typology_counts: Record<string, number>;
  score_15min_mean?: number | null;
}

// A Plotly figure spec as produced by fig.to_json() server-side.
export interface PlotlySpec {
  data: object[];
  layout: Record<string, unknown>;
}

export interface AnalysisResult {
  city_name: string;
  config: Record<string, unknown>;
  metrics_summary: MetricsSummary;
  scalars: Scalars;
  charts: Record<string, PlotlySpec>;
  district_scores: Record<string, unknown>[];
  warnings: string[];
}

export interface CompareResult {
  kind: "compare";
  city_a: AnalysisResult;
  city_b: AnalysisResult;
  diff_summary: Record<string, { city_a: number; city_b: number; delta: number }>;
}

export type JobStatus = "pending" | "running" | "done" | "error";

export interface JobPoll<T = AnalysisResult> {
  status: JobStatus;
  progress?: string | null;
  result: T | null;
  error: string | null;
}

export interface SharedAnalysis {
  id: string;
  city_name: string;
  created_at: string | null;
  result: AnalysisResult | CompareResult;
}

// Config sent to POST /api/analyze — mirrors the v1 sidebar.
export interface AnalyzeConfig {
  city_size?: string;
  zone_mode?: string;
  selected_district?: string;
  custom_bbox?: [number, number, number, number];
  morphology?: boolean;
  transport?: boolean;
  nature?: boolean;
  terrain?: boolean;
  climate?: boolean;
  stress_index?: boolean;
  fabric_typology?: boolean;
  cross_analysis?: boolean;
}

export const CITY_SIZES = [
  "Small (< 100k)",
  "Medium (100k–500k)",
  "Large (500k+)",
] as const;

// API zone_mode values (what pipeline.py expects) with their UI labels.
export const ZONE_MODES = [
  { value: "Entire city", label: "Entire city" },
  { value: "Select district", label: "District" },
  { value: "Draw custom bbox", label: "Custom area" },
] as const;

export interface DistrictsResponse {
  level_used: number | null;
  districts: { name: string; osm_id: string }[];
  city_bbox: [number, number, number, number] | null;
}

export const MODULE_TOGGLES: { key: keyof AnalyzeConfig; label: string }[] = [
  { key: "morphology", label: "Morphology & Buildings" },
  { key: "transport", label: "Transport & Accessibility" },
  { key: "nature", label: "Nature & Green Space" },
  { key: "terrain", label: "Terrain & Flood Risk" },
  { key: "climate", label: "Climate & Heat Island" },
  { key: "stress_index", label: "Urban Stress Index" },
  { key: "fabric_typology", label: "Urban Fabric Typology" },
  { key: "cross_analysis", label: "Cross-Analysis" },
];
