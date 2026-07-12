"use client";

import { useState } from "react";
import { compare, waitForJob } from "@/lib/api";
import { addHistory } from "@/lib/history";
import type { CompareResult } from "@/lib/types";
import AnalysisTabs from "@/components/AnalysisTabs";
import ProgressPanel from "@/components/ProgressPanel";

const DIFF_LABELS: Record<string, string> = {
  total_buildings: "Buildings",
  total_pois: "POIs",
  median_height: "Median height (m)",
  green_space_pct: "Green space (%)",
  transport_index_mean: "Transport index",
  urban_stress_mean: "Urban stress",
};

type Phase =
  | { kind: "idle" }
  | { kind: "running"; progress: string }
  | { kind: "done"; result: CompareResult }
  | { kind: "error"; message: string };

export default function ComparePage() {
  const [cityA, setCityA] = useState("");
  const [cityB, setCityB] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });

  const run = async () => {
    setPhase({ kind: "running", progress: "" });
    try {
      const { job_id } = await compare(cityA.trim(), cityB.trim(), {});
      addHistory({
        jobId: job_id,
        cityName: `${cityA.trim()} vs ${cityB.trim()}`,
        kind: "compare",
        createdAt: new Date().toISOString(),
      });
      const result = await waitForJob<CompareResult>(job_id, (progress) =>
        setPhase({ kind: "running", progress }),
      );
      setPhase({ kind: "done", result });
    } catch (e) {
      setPhase({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <main className="mx-auto max-w-[1600px] px-4 py-4 space-y-4">
      <h1 className="font-mono text-sm uppercase tracking-widest text-ink-dim">
        City Comparison
      </h1>
      <div className="panel p-4 flex flex-wrap items-end gap-3">
        <label className="space-y-1 flex-1 min-w-[220px]">
          <span className="text-xs text-ink-dim">City A</span>
          <input className="input-dark" placeholder="e.g. Blois, France"
            value={cityA} onChange={(e) => setCityA(e.target.value)} />
        </label>
        <label className="space-y-1 flex-1 min-w-[220px]">
          <span className="text-xs text-ink-dim">City B</span>
          <input className="input-dark" placeholder="e.g. Tours, France"
            value={cityB} onChange={(e) => setCityB(e.target.value)} />
        </label>
        <button
          className="btn-primary"
          disabled={phase.kind === "running" || !cityA.trim() || !cityB.trim()}
          onClick={run}
        >
          {phase.kind === "running" ? "Comparing…" : "Compare"}
        </button>
      </div>

      {phase.kind === "running" && (
        <ProgressPanel cityName={`${cityA} vs ${cityB}`} progress={phase.progress} />
      )}
      {phase.kind === "error" && (
        <div className="panel border-accent-risk/40 p-6 text-sm text-accent-risk font-mono">
          {phase.message}
        </div>
      )}

      {phase.kind === "done" && (
        <>
          {/* Diff summary */}
          <div className="panel p-4 overflow-x-auto">
            <div className="stat-label mb-3">Numeric deltas (B − A)</div>
            <table className="w-full text-sm font-mono">
              <thead>
                <tr className="text-ink-dim text-left text-xs">
                  <th className="pb-2">Metric</th>
                  <th className="pb-2">{phase.result.city_a.city_name}</th>
                  <th className="pb-2">{phase.result.city_b.city_name}</th>
                  <th className="pb-2">Δ</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(phase.result.diff_summary).map(([k, v]) => (
                  <tr key={k} className="border-t border-edge">
                    <td className="py-1.5 text-ink-dim">{DIFF_LABELS[k] ?? k}</td>
                    <td className="py-1.5">{Number(v.city_a).toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
                    <td className="py-1.5">{Number(v.city_b).toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
                    <td className={`py-1.5 ${v.delta >= 0 ? "text-accent-transport" : "text-accent-poi"}`}>
                      {v.delta >= 0 ? "+" : ""}
                      {Number(v.delta).toLocaleString(undefined, { maximumFractionDigits: 3 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Side-by-side full results */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {([phase.result.city_a, phase.result.city_b] as const).map((r, i) => (
              <div key={i} className="min-w-0 space-y-2">
                <h2 className="font-mono text-sm text-ink border-b border-edge pb-1.5">
                  {r.city_name}
                </h2>
                <AnalysisTabs result={r} />
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
