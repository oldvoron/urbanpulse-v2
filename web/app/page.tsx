"use client";

// Main analyze view: v1 sidebar + 9-tab result view, backed by
// POST /api/analyze + polling instead of a blocking Streamlit rerun.

import { useRef, useState } from "react";
import { analyze, waitForJob } from "@/lib/api";
import { addHistory } from "@/lib/history";
import type { AnalysisResult } from "@/lib/types";
import ControlPanel, {
  ControlState,
  controlsToConfig,
  defaultControls,
} from "@/components/ControlPanel";
import AnalysisTabs from "@/components/AnalysisTabs";
import ProgressPanel from "@/components/ProgressPanel";
import ExportBar from "@/components/ExportBar";
import { InfoDrawer } from "@/components/InfoPanels";

type Phase =
  | { kind: "idle" }
  | { kind: "running"; city: string; progress: string }
  | { kind: "done"; jobId: string; result: AnalysisResult }
  | { kind: "error"; message: string };

export default function AnalyzePage() {
  const [controls, setControls] = useState<ControlState>(defaultControls);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const runSeq = useRef(0);

  const run = async () => {
    const seq = ++runSeq.current;
    const city = controls.cityName.trim();
    setPhase({ kind: "running", city, progress: "" });
    try {
      const { job_id } = await analyze(city, controls.zoneMode, controlsToConfig(controls));
      addHistory({
        jobId: job_id,
        cityName: city,
        kind: "analyze",
        createdAt: new Date().toISOString(),
      });
      const result = await waitForJob<AnalysisResult>(job_id, (progress) => {
        if (runSeq.current === seq)
          setPhase({ kind: "running", city, progress });
      });
      if (runSeq.current === seq) setPhase({ kind: "done", jobId: job_id, result });
    } catch (e) {
      if (runSeq.current === seq)
        setPhase({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <main className="mx-auto max-w-[1600px] px-4 py-4">
      <div className="flex items-center justify-between mb-3">
        <h1 className="font-mono text-sm uppercase tracking-widest text-ink-dim">
          Urban Spatial Analytics
        </h1>
        <InfoDrawer />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
        <ControlPanel
          state={controls}
          onChange={setControls}
          onAnalyze={run}
          busy={phase.kind === "running"}
        />
        <section className="min-w-0">
          {phase.kind === "idle" && (
            <div className="panel p-10 text-center text-ink-dim text-sm">
              Enter a city name and click <span className="text-accent-transport">Analyze</span> to begin.
            </div>
          )}
          {phase.kind === "running" && (
            <ProgressPanel cityName={phase.city} progress={phase.progress} />
          )}
          {phase.kind === "error" && (
            <div className="panel border-accent-risk/40 p-6 text-sm text-accent-risk font-mono">
              {phase.message}
            </div>
          )}
          {phase.kind === "done" && (
            <div className="space-y-3">
              <ExportBar jobId={phase.jobId} cityName={phase.result.city_name} />
              <AnalysisTabs result={phase.result} />
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
