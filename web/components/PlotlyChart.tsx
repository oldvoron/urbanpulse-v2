"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { PlotlySpec } from "@/lib/types";
import { CHART_CAPTIONS } from "@/lib/captions";

// react-plotly.js factory + plotly.js-dist-min: the bundled minified build,
// loaded client-side only (Plotly can't render during SSR).
const Plot = dynamic(
  async () => {
    const [{ default: createPlotlyComponent }, { default: Plotly }] =
      await Promise.all([
        import("react-plotly.js/factory"),
        import("plotly.js-dist-min"),
      ]);
    return createPlotlyComponent(Plotly);
  },
  {
    ssr: false,
    loading: () => (
      <div className="h-64 flex items-center justify-center text-ink-faint text-sm font-mono">
        loading chart…
      </div>
    ),
  },
);

/**
 * Renders a Plotly figure spec straight from the API (no chart logic is
 * reimplemented in TS — brief §4.4) inside a panel card, re-themed for the
 * dark UI: transparent paper, panel-colored plot area, CARTO dark-matter
 * basemap for map charts (§6). Data traces and colorscales are left exactly
 * as the engine produced them.
 */
export default function PlotlyChart({
  name,
  spec,
  showCaption = true,
}: {
  name: string;
  spec: PlotlySpec;
  showCaption?: boolean;
}) {
  const themed = useMemo(() => {
    // NOTE: plotly.js is pinned to 2.x — the engine emits figure JSON from
    // plotly.py 5.x, whose *mapbox traces are native in 2.x but crash in 3.x.
    const data = spec.data;

    const layout: Record<string, unknown> = {
      ...spec.layout,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "#10151E",
      font: { ...(spec.layout.font as object), color: "#D7DEE8" },
      autosize: true,
    };
    delete layout.width;
    delete layout.height;
    for (const axis of ["xaxis", "yaxis", "xaxis2", "yaxis2"]) {
      if (layout[axis] && typeof layout[axis] === "object") {
        layout[axis] = {
          ...(layout[axis] as object),
          gridcolor: "#1E2735",
          zerolinecolor: "#1E2735",
        };
      }
    }
    // Map charts → CARTO dark-matter tiles (free, no API key)
    if (layout.mapbox && typeof layout.mapbox === "object") {
      layout.mapbox = { ...(layout.mapbox as object), style: "carto-darkmatter" };
    }
    if (layout.polar && typeof layout.polar === "object") {
      layout.polar = {
        ...(layout.polar as object),
        bgcolor: "#10151E",
      };
    }
    if (layout.legend && typeof layout.legend === "object") {
      layout.legend = { ...(layout.legend as object), bgcolor: "rgba(0,0,0,0)" };
    }
    return { data, layout };
  }, [spec]);

  return (
    <figure className="panel p-3">
      {/* Fixed height + overflow-hidden (§1.1): even if a label calculation
          is imperfect, it clips instead of bleeding into a sibling panel. */}
      <div className="overflow-hidden" style={{ height: 420 }}>
        <Plot
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data={themed.data as any}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          layout={themed.layout as any}
          config={{ displaylogo: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
        />
      </div>
      {showCaption && CHART_CAPTIONS[name] && (
        <figcaption className="caption px-1">{CHART_CAPTIONS[name]}</figcaption>
      )}
    </figure>
  );
}
