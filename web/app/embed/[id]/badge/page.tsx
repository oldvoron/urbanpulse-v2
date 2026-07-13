// Minimal iframe-embeddable badge (Addendum 2 §9): a single-stat variant of
// the /embed/[id] white-label view, linking back to the full analysis.
// Server-rendered so third-party pages get instant content in the iframe.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:7860";

const METRIC_LABELS: Record<string, { label: string; fmt: (v: number) => string }> = {
  green_space_pct: { label: "Green Space", fmt: (v) => `${v.toFixed(1)}%` },
  total_buildings: { label: "Buildings", fmt: (v) => v.toLocaleString() },
  total_pois: { label: "POIs", fmt: (v) => v.toLocaleString() },
  urban_stress_mean: { label: "Urban Stress", fmt: (v) => v.toFixed(2) },
};

export default async function BadgePage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { metric?: string };
}) {
  let cityName = "";
  let value: string | null = null;
  const metricKey =
    searchParams.metric && METRIC_LABELS[searchParams.metric]
      ? searchParams.metric
      : "green_space_pct";
  const metric = METRIC_LABELS[metricKey];

  try {
    const res = await fetch(`${API_URL}/api/analysis/${params.id}`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const data = await res.json();
      cityName = data.city_name;
      const raw = data.result?.metrics_summary?.[metricKey];
      if (typeof raw === "number") value = metric.fmt(raw);
    }
  } catch {
    /* badge renders its fallback */
  }

  return (
    <a
      href={`/analysis/${params.id}`}
      target="_blank"
      className="flex items-center gap-3 px-4 py-2.5 bg-panel border border-edge rounded-md
        hover:border-accent-transport/50 transition-colors w-fit m-1"
    >
      <span className="font-mono text-xs font-bold tracking-tight text-ink">
        URBAN<span className="text-accent-transport">PULSE</span>
      </span>
      {value !== null ? (
        <span className="text-xs text-ink-dim">
          {cityName} — {metric.label}:{" "}
          <span className="font-mono text-accent-nature font-bold">{value}</span>
        </span>
      ) : (
        <span className="text-xs text-ink-faint">analysis unavailable</span>
      )}
      <span className="text-[10px] text-ink-faint font-mono">↗</span>
    </a>
  );
}
