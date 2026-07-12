// Typed client wrapping fetch calls to the FastAPI backend.
import type {
  AnalyzeConfig,
  AnalysisResult,
  CompareResult,
  DistrictsResponse,
  JobPoll,
  SharedAnalysis,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:7860";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function analyze(
  cityName: string,
  zoneMode: string,
  config: AnalyzeConfig,
): Promise<{ job_id: string }> {
  return jsonFetch("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ city_name: cityName, zone_mode: zoneMode, config }),
  });
}

export function pollJob<T = AnalysisResult>(jobId: string): Promise<JobPoll<T>> {
  return jsonFetch(`/api/analyze/${jobId}`);
}

export function compare(
  cityA: string,
  cityB: string,
  config: AnalyzeConfig,
): Promise<{ job_id: string }> {
  return jsonFetch("/api/compare", {
    method: "POST",
    body: JSON.stringify({ city_a: cityA, city_b: cityB, config }),
  });
}

/** Poll a job every `intervalMs` until done/error. Returns the final result. */
export async function waitForJob<T = AnalysisResult | CompareResult>(
  jobId: string,
  onProgress?: (msg: string) => void,
  intervalMs = 2500,
): Promise<T> {
  for (;;) {
    const poll = await pollJob<T>(jobId);
    if (poll.status === "done" && poll.result) return poll.result;
    if (poll.status === "error") throw new Error(poll.error || "Analysis failed");
    if (onProgress && poll.progress) onProgress(poll.progress);
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export function exportDataUrl(jobId: string, format: "geojson" | "shapefile"): string {
  return `${API_URL}/api/export/${jobId}?format=${format}`;
}

export async function getReport(jobId: string): Promise<Blob> {
  const res = await fetch(`${API_URL}/api/report/${jobId}`, { method: "POST" });
  if (!res.ok) throw new Error(`Report failed: ${res.status}`);
  return res.blob();
}

export function getSharedAnalysis(id: string): Promise<SharedAnalysis> {
  return jsonFetch(`/api/analysis/${id}`);
}

export function getDistricts(cityName: string): Promise<DistrictsResponse> {
  return jsonFetch(`/api/districts?city_name=${encodeURIComponent(cityName)}`);
}
