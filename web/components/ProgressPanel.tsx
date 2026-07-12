"use client";

export default function ProgressPanel({
  cityName,
  progress,
}: {
  cityName: string;
  progress: string;
}) {
  return (
    <div className="panel p-8 flex flex-col items-center gap-4">
      <div className="flex gap-1.5">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="w-2 h-2 rounded-full bg-accent-transport animate-pulse"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
      <div className="font-mono text-sm text-ink">{cityName}</div>
      <div className="font-mono text-xs text-ink-dim min-h-[1rem]">
        {progress || "Queued…"}
      </div>
      <p className="text-[11px] text-ink-faint max-w-sm text-center">
        Fetching live OSM / Overture data and computing spatial analytics — a
        first-time analysis takes 2–6 minutes. Repeat runs hit the city cache
        and are much faster.
      </p>
    </div>
  );
}
