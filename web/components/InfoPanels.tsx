"use client";

// About / Methodology side panels + first-visit onboarding modal.

import { useEffect, useState } from "react";

const ONBOARD_KEY = "urbanpulse.instructions.v1";

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
      <p className="text-ink-faint text-xs border-t border-edge pt-3">
        Built by Vasilii Kurian — urban planning researcher (Tours, France).
        <br />
        Contact:{" "}
        <a href="mailto:vasiliikurian@gmail.com" className="text-accent-transport">
          vasiliikurian@gmail.com
        </a>
      </p>
    </div>
  );
}

export function InstructionsPanel() {
  const steps: [string, React.ReactNode][] = [
    [
      "1. Enter a city",
      <>Type a city name with its country, e.g. “Blois, France”. Country
      disambiguates cities that share a name across countries.</>,
    ],
    [
      "2. Choose an analysis zone",
      <>
        <span className="text-ink">Entire city</span> — analyzes the full
        OSM-defined city boundary.{" "}
        <span className="text-ink">District</span> — pick a real administrative
        subdivision (arrondissement, borough, district — whatever the local
        system calls it) from a list generated for that specific city.{" "}
        <span className="text-ink">Custom area</span> — draw a rectangle
        directly on the map.
      </>,
    ],
    [
      "3. Click Analyze",
      <>The app fetches live data from OpenStreetMap and Overture Maps and
      computes every metric on demand — nothing is precomputed, so the first
      run on a new city takes longer than a cached one.</>,
    ],
    [
      "4. Explore the tabs",
      <>Overview, Morphology, Street Network, Transport, Nature &amp; Risk,
      Cross-Analysis, Stress &amp; Risk, Typology, District Scores.</>,
    ],
    [
      "5. Export or share",
      <>Download a PDF report, export raw data as GeoJSON/Shapefile for use in
      QGIS, or copy a shareable link to this exact analysis.</>,
    ],
  ];
  return (
    <div className="space-y-3">
      {steps.map(([title, body]) => (
        <div key={title}>
          <div className="stat-label">{title}</div>
          <p className="text-xs text-ink-dim leading-relaxed mt-0.5">{body}</p>
        </div>
      ))}
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

type PanelKind = "about" | "methodology" | "instructions";

const PANEL_TITLES: Record<PanelKind, string> = {
  about: "About",
  methodology: "Methodology",
  instructions: "Instructions",
};

export function InfoDrawer() {
  const [open, setOpen] = useState<null | PanelKind>(null);

  // §1.6: Instructions auto-opens on a user's first visit (localStorage flag,
  // independent of the placeholder account system), dismissible, and
  // reachable again anytime via the header button.
  useEffect(() => {
    if (!localStorage.getItem(ONBOARD_KEY)) {
      setOpen("instructions");
      localStorage.setItem(ONBOARD_KEY, "1");
    }
  }, []);

  return (
    <>
      <div className="flex gap-2">
        {(Object.keys(PANEL_TITLES) as PanelKind[]).map((k) => (
          <button key={k} className="btn-ghost !text-xs" onClick={() => setOpen(k)}>
            {PANEL_TITLES[k]}
          </button>
        ))}
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
                {PANEL_TITLES[open]}
              </h2>
              <button className="btn-ghost !px-2 !py-0.5" onClick={() => setOpen(null)}>
                ✕
              </button>
            </div>
            {open === "about" && <AboutPanel />}
            {open === "methodology" && <MethodologyPanel />}
            {open === "instructions" && <InstructionsPanel />}
          </div>
        </div>
      )}
    </>
  );
}
