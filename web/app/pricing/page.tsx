"use client";

// Static pricing tiers copy; "Upgrade" opens the §0 placeholder modal only.

import {
  PlaceholderModalProvider,
  UpgradeButton,
} from "@/components/PlaceholderAuthModal";

const TIERS = [
  {
    name: "Explorer",
    price: "€0",
    period: "forever",
    features: [
      "Full 9-tab analysis for any city",
      "City comparison",
      "GeoJSON / Shapefile / PDF export",
      "Shareable analysis links",
    ],
    cta: "Current plan",
    highlighted: false,
  },
  {
    name: "Studio",
    price: "€19",
    period: "per month",
    features: [
      "Everything in Explorer",
      "Saved analysis history across devices",
      "White-label embeds without attribution",
      "Priority compute queue",
      "Batch city analysis",
    ],
    cta: "Upgrade",
    highlighted: true,
  },
  {
    name: "Practice",
    price: "€79",
    period: "per month",
    features: [
      "Everything in Studio",
      "API access",
      "Custom analysis zones & bulk export",
      "Team seats",
      "Support SLA",
    ],
    cta: "Upgrade",
    highlighted: false,
  },
];

export default function PricingPage() {
  return (
    <PlaceholderModalProvider>
      <main className="mx-auto max-w-5xl px-4 py-10 space-y-8">
        <div className="text-center space-y-2">
          <h1 className="font-mono text-sm uppercase tracking-widest text-ink-dim">
            Pricing
          </h1>
          <p className="text-2xl text-ink font-medium">
            Spatial analytics for every practice size
          </p>
          <p className="text-sm text-ink-faint">
            Billing isn&apos;t live yet — every feature marked free is genuinely free today.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={`panel p-6 flex flex-col gap-4 ${
                t.highlighted ? "border-accent-transport/50" : ""
              }`}
            >
              <div>
                <div className="stat-label">{t.name}</div>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className="font-mono text-3xl text-ink">{t.price}</span>
                  <span className="text-xs text-ink-faint">/ {t.period}</span>
                </div>
              </div>
              <ul className="text-sm text-ink-dim space-y-1.5 flex-1">
                {t.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-accent-transport">·</span>
                    {f}
                  </li>
                ))}
              </ul>
              {t.cta === "Upgrade" ? (
                <UpgradeButton />
              ) : (
                <div className="text-center text-xs font-mono text-ink-faint border border-edge rounded py-2">
                  {t.cta}
                </div>
              )}
            </div>
          ))}
        </div>
      </main>
    </PlaceholderModalProvider>
  );
}
