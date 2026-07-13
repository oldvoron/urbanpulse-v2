"use client";

// Shared renderer for /analysis/[id] (full chrome) and /embed/[id]
// (chrome-less iframe variant). Fetches a completed job by its public id.

import { useEffect, useState } from "react";
import { getSharedAnalysis } from "@/lib/api";
import type { AnalysisResult, CompareResult, SharedAnalysis } from "@/lib/types";
import AnalysisTabs from "./AnalysisTabs";
import ExportBar from "./ExportBar";

function isCompare(r: AnalysisResult | CompareResult): r is CompareResult {
  return (r as CompareResult).kind === "compare";
}

export default function SharedAnalysisView({
  id,
  embed = false,
  hideHeader = false,
}: {
  id: string;
  embed?: boolean;
  hideHeader?: boolean;
}) {
  const [data, setData] = useState<SharedAnalysis | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSharedAnalysis(id)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  if (error)
    return (
      <div className="panel border-accent-risk/40 p-8 text-center text-sm text-accent-risk font-mono m-4">
        {error === "Analysis not found"
          ? "This analysis doesn't exist (or hasn't finished)."
          : error}
      </div>
    );
  if (!data)
    return (
      <div className="p-10 text-center font-mono text-sm text-ink-dim">
        loading analysis…
      </div>
    );

  const r = data.result;
  return (
    <div className={embed ? "p-2" : "space-y-3"}>
      {!embed && !hideHeader && (
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-lg text-ink font-medium">{data.city_name}</h1>
          <span className="font-mono text-[11px] text-ink-faint">
            {data.created_at && new Date(data.created_at).toLocaleString()} · shared analysis
          </span>
        </div>
      )}
      {isCompare(r) ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {[r.city_a, r.city_b].map((cr, i) => (
            <div key={i} className="min-w-0 space-y-2">
              <h2 className="font-mono text-sm text-ink border-b border-edge pb-1.5">
                {cr.city_name}
              </h2>
              <AnalysisTabs result={cr} />
            </div>
          ))}
        </div>
      ) : (
        <>
          {!embed && <ExportBar jobId={data.id} cityName={data.city_name} />}
          <AnalysisTabs result={r} />
        </>
      )}
      {embed && (
        <a
          href={`/analysis/${id}`}
          target="_blank"
          className="block text-right font-mono text-[10px] text-ink-faint hover:text-accent-transport pt-1"
        >
          Urban Pulse ↗
        </a>
      )}
    </div>
  );
}
