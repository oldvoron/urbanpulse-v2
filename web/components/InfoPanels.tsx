"use client";

// About / Methodology side panels + first-visit onboarding modal.

import { useEffect, useState } from "react";

const ONBOARD_KEY = "urbanpulse.onboarded.v2";

export function AboutPanel() {
  return (
    <div className="space-y-3 text-sm text-ink-dim leading-relaxed">
      <p>
        <span className="text-ink font-medium">Urban Pulse</span> computes real
        spatial analytics for any city from open data: urban morphology, street
        network structure, transport accessibility, nature and green space,
        terrain and flood proxies, an urban stress index, fabric typology, and
        per-district scores.
      </p>
      <p>
        Data sources: Overture Maps Places, OpenStreetMap (via Overpass),
        Open-Meteo elevation and forecast APIs. Analyses run on demand — nothing
        is precomputed, so any city with OSM coverage works.
      </p>
      <p className="text-ink-faint text-xs">
        Colour-coding across the app is descriptive per data category — cyan for
        transport, magenta for POI/functional zones, amber for risk readouts,
        green reserved for nature — never an evaluative good/bad scale.
      </p>
    </div>
  );
}

export function MethodologyPanel() {
  const items: [string, string][] = [
    [
      "Hex grid",
      "All spatial indices aggregate to H3 hexagons (resolution 8–9, ~460–170m). Metrics join on cell id; maps clip to the OSM city boundary.",
    ],
    [
      "Morphology",
      "FAR = built floor area ÷ cell area (floors = height/3.5m). Morphotypes: KMeans (k=5) over FAR, coverage, height, street density, POI density, land-use diversity.",
    ],
    [
      "Transport",
      "Composite of transit-stop density in 400m walk (50%), cycling km/km² (30%), road-type entropy (20%).",
    ],
    [
      "Nature",
      "Green space ratio per cell from OSM leisure/landuse/natural polygons; park access, water proximity, and a waterway-buffer flood proxy.",
    ],
    [
      "Urban stress",
      "Five equally weighted components: density stress, green deficit, transit deficit, flood stress, mono-functionality.",
    ],
    [
      "Proxies, not measurements",
      "Heat island, flood risk, vulnerability, and segregation indices are structural proxies computed from built form — not sensor data or official hazard maps.",
    ],
  ];
  return (
    <div className="space-y-3">
      {items.map(([title, body]) => (
        <div key={title}>
          <div className="stat-label">{title}</div>
          <p className="text-xs text-ink-dim leading-relaxed mt-0.5">{body}</p>
        </div>
      ))}
    </div>
  );
}

export function InfoDrawer() {
  const [open, setOpen] = useState<null | "about" | "methodology">(null);
  return (
    <>
      <div className="flex gap-2">
        <button className="btn-ghost !text-xs" onClick={() => setOpen("about")}>
          About
        </button>
        <button className="btn-ghost !text-xs" onClick={() => setOpen("methodology")}>
          Methodology
        </button>
      </div>
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex justify-end"
          onClick={() => setOpen(null)}
        >
          <div
            className="bg-panel border-l border-edge w-full max-w-md h-full overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-mono text-sm uppercase tracking-widest text-ink">
                {open === "about" ? "About" : "Methodology"}
              </h2>
              <button className="btn-ghost !px-2 !py-0.5" onClick={() => setOpen(null)}>
                ✕
              </button>
            </div>
            {open === "about" ? <AboutPanel /> : <MethodologyPanel />}
          </div>
        </div>
      )}
    </>
  );
}

export function OnboardingModal() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!localStorage.getItem(ONBOARD_KEY)) setShow(true);
  }, []);
  if (!show) return null;
  const dismiss = () => {
    localStorage.setItem(ONBOARD_KEY, "1");
    setShow(false);
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center" onClick={dismiss}>
      <div className="panel max-w-lg w-[92%] p-6" onClick={(e) => e.stopPropagation()}>
        <div className="font-mono text-xs uppercase tracking-widest text-accent-transport mb-3">
          Welcome to Urban Pulse
        </div>
        <ol className="text-sm text-ink-dim space-y-2 list-decimal list-inside leading-relaxed">
          <li>
            Type a city name <span className="text-ink-faint">(include the country — “Blois, France”)</span> and
            hit <span className="text-accent-transport">Analyze</span>.
          </li>
          <li>Live OSM + Overture data is fetched and analysed — first runs take a few minutes.</li>
          <li>Explore nine tabs of maps and indices, export GeoJSON/Shapefile/PDF, or share the result with a permanent link.</li>
          <li>
            Use <span className="text-ink">Compare</span> to put two cities side by side.
          </li>
        </ol>
        <button className="btn-primary mt-5 w-full" onClick={dismiss}>
          Start analysing
        </button>
      </div>
    </div>
  );
}
