// Public shareable analysis view — SERVER-RENDERED (Addendum 2 §6): the city
// name, key figures, and chart captions are in the initial HTML response so
// the page is crawlable, with unique title/description/Open Graph tags per
// analysis. Interactive charts hydrate client-side on top.

import type { Metadata } from "next";
import SharedAnalysisView from "@/components/SharedAnalysisView";
import { CHART_CAPTIONS } from "@/lib/captions";
import StatTile from "@/components/StatTile";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:7860";

interface Shared {
  id: string;
  city_name: string;
  created_at: string | null;
  result: {
    kind?: string;
    metrics_summary?: {
      total_buildings: number;
      total_pois: number;
      green_space_pct: number;
      urban_stress_mean: number;
      dominant_morphotype: string;
    };
    charts?: Record<string, unknown>;
  };
}

// Next.js dedupes this fetch between generateMetadata and the page render;
// completed analyses are immutable, so a long revalidate is safe.
async function fetchAnalysis(id: string): Promise<Shared | null> {
  try {
    const res = await fetch(`${API_URL}/api/analysis/${id}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return (await res.json()) as Shared;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const data = await fetchAnalysis(params.id);
  if (!data) return { title: "Analysis not found | Urban Pulse" };
  const ms = data.result?.metrics_summary;
  const title = `${data.city_name} — Urban Spatial Analysis | Urban Pulse`;
  const description = ms
    ? `Open-data urban analytics for ${data.city_name}: ${ms.total_buildings.toLocaleString()} buildings, ` +
      `${ms.green_space_pct.toFixed(1)}% green space, dominant morphotype ${ms.dominant_morphotype}. ` +
      `Morphology, street network, transport accessibility, nature, urban stress and fabric typology.`
    : `Urban spatial analysis of ${data.city_name} from OpenStreetMap and Overture Maps data.`;
  const cardUrl = `${API_URL}/api/card/${params.id}`;
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      images: [{ url: cardUrl, width: 1200, height: 630 }],
    },
    twitter: { card: "summary_large_image", title, description, images: [cardUrl] },
  };
}

export default async function SharedAnalysisPage({
  params,
}: {
  params: { id: string };
}) {
  const data = await fetchAnalysis(params.id);
  const ms = data?.result?.metrics_summary;
  const chartKeys = Object.keys(data?.result?.charts ?? {});

  return (
    <main className="mx-auto max-w-[1600px] px-4 py-4 space-y-3">
      {data && (
        <>
          {/* Server-rendered summary: present in the initial HTML for crawlers */}
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h1 className="text-lg text-ink font-medium">
              {data.city_name} — Urban Spatial Analysis
            </h1>
            <span className="font-mono text-[11px] text-ink-faint">
              {data.created_at && new Date(data.created_at).toLocaleDateString()} ·
              shared analysis
            </span>
          </div>
          {ms && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatTile label="Total Buildings" value={ms.total_buildings.toLocaleString()} />
              <StatTile label="Total POIs" value={ms.total_pois.toLocaleString()} accent="poi" />
              <StatTile label="Green Space" value={`${ms.green_space_pct.toFixed(1)}%`} accent="nature" />
              <StatTile label="Dominant Morphotype" value={ms.dominant_morphotype} />
            </div>
          )}
        </>
      )}

      <SharedAnalysisView id={params.id} hideHeader />

      {/* Crawlable chart descriptions (same captions shown in the UI) */}
      {chartKeys.length > 0 && (
        <section className="panel p-4 mt-4">
          <h2 className="stat-label mb-3">About the charts in this analysis</h2>
          <dl className="space-y-2">
            {chartKeys
              .filter((k) => CHART_CAPTIONS[k])
              .map((k) => (
                <div key={k}>
                  <dt className="text-xs text-ink-dim font-medium">
                    {k.replace(/_/g, " ")}
                  </dt>
                  <dd className="text-[11px] text-ink-faint leading-relaxed">
                    {CHART_CAPTIONS[k]}
                  </dd>
                </div>
              ))}
          </dl>
        </section>
      )}
    </main>
  );
}
