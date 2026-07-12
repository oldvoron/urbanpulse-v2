import type { Config } from "tailwindcss";

// "Situation room" design system (build brief §6).
// Accents are bound to DATA CATEGORIES, not to charts or moods, and are
// descriptive — never evaluative (no red=bad / green=good binary):
//   accent-transport → transport / network
//   accent-poi       → POI / functional zones
//   accent-risk      → risk / stress readouts
//   accent-nature    → nature / green space ONLY
// Components must reference these semantic names, never raw hexes.
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base: "#0B0F16",        // near-black page background (not pure #000)
        panel: "#10151E",       // card / panel surface
        "panel-2": "#141B26",   // raised surface
        edge: "#1E2735",        // hairline borders
        ink: "#D7DEE8",         // primary text
        "ink-dim": "#8A94A6",   // secondary text
        "ink-faint": "#5A6478", // tertiary / captions
        "accent-transport": "#2DD4EF",
        "accent-poi": "#E86BF0",
        "accent-risk": "#F5A623",
        "accent-nature": "#3ECF8E",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
